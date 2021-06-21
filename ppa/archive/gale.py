import logging
import time

import pymarc
import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pairtree import PairtreeStorageFactory, storage_exceptions

from ppa import __version__ as ppa_version

logger = logging.getLogger(__name__)


class GaleAPIError(Exception):
    """Base exception class for Gale API errors"""


class GaleItemForbidden(GaleAPIError):
    """Permission denied to access item in Gale API"""


class GaleUnauthorized(GaleAPIError):
    """Permission not authorized for Gale API access"""


class GaleItemNotFound(GaleAPIError):
    """Item not found in Gale API"""


class GaleAPI:
    """Minimal Gale API client with functionality need for PPA import.

    Requires **GALE_API_USERNAME** configured in Django settings. Automatically
    uses the configured username to retrieve an API key when needed, and has
    logic to refresh the API key when it expires (30 minutes).

    If **TECHNICAL_CONTACT** is configured in Django settings, it will
    be included in request headers when making API calls.

    Implemented as a singleton; instanciating the class will return the
    same shared instance every time.
    """

    #: base URL for all API requests
    api_root = "https://api.gale.com/api"

    #: shared singleton instance; populated on first instantiation
    instance = None

    def __new__(cls):
        # implement as a singleton
        # adapted from https://softwareengineering.stackexchange.com/a/333710

        # if no instance has been initialized, create and store on the class
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        # return the instance
        return cls.instance

    def __init__(self):
        # NOTE: copied from hathi.py base api class; should be generalized
        # into a common base class if/when we add a third provider

        # first make sure we have a username configured
        try:
            self.username = settings.GALE_API_USERNAME
        except AttributeError:
            raise ImproperlyConfigured(
                "GALE_API_USERNAME configuration is required for Gale API"
            )

        # create a request session, for request pooling
        self.session = requests.Session()
        # set a user-agent header, but  preserve requests version information
        headers = {
            "User-Agent": "ppa-django/%s (%s)"
            % (ppa_version, self.session.headers["User-Agent"])
        }
        # include technical contact as From header, if set
        tech_contact = getattr(settings, "TECHNICAL_CONTACT", None)
        if tech_contact:
            headers["From"] = tech_contact
        self.session.headers.update(headers)

    def _make_request(
        self, url, params=None, requires_api_key=True, stream=False, retry=0
    ):
        """Make a GET request with the configured session. Takes a url
        relative to :attr:`api_root`, optional dictionary of parameters for the request,
        and flags to indicate if the request needs an API key, should be streamed,
        or is a retry."""
        # NOTE: also copied from hathi.py

        # Returns the response for status 200 OK; raises
        # :class:`HathiItemNotFound` for 404 and :class:`HathiItemForbidden`
        # for 403.
        # '''
        rqst_url = "%s/%s" % (self.api_root, url)
        rqst_opts = {}
        if params:
            rqst_opts["params"] = params.copy()

        # add api key to parameters if neded for this request
        if requires_api_key:
            if "params" not in rqst_opts:
                rqst_opts["params"] = {}
            rqst_opts["params"]["api_key"] = self.api_key

        resp = self.session.get(rqst_url, stream=stream, **rqst_opts)
        logger.debug(
            "get %s %s: %f sec",
            rqst_url,
            resp.status_code,
            resp.elapsed.total_seconds(),
        )
        if resp.status_code == requests.codes.ok:
            return resp
        if resp.status_code == requests.codes.not_found:
            raise GaleItemNotFound

        # when api key expires, API returns:
        # HTTP Status 401 - Authentication Failed: Invalid or Expired API key
        # If we get a 401 on a request that requires an api key, try getting a new one
        if resp.status_code == requests.codes.unauthorized:
            # If we get a 401 on a request that requires an api key,
            # get a fresh key and then try the same request again
            if requires_api_key and retry < 1:
                self.refresh_api_key()
                return self._make_request(
                    url,
                    params=params,
                    requires_api_key=requires_api_key,
                    stream=stream,
                    retry=retry + 1,
                )
            # response is html error, not json; could try
            # extracting h1, but not sure it's worth parsing
            raise GaleUnauthorized()

        if resp.status_code == requests.codes.forbidden:
            # forbidden results return a message
            # NOTE that item requests for invalid ids may return 403
            raise GaleItemForbidden(resp.json()["message"])

        # raise anything else as a generic error with status code
        # getting 406 not acceptable in some cases
        # (attempt to access item with invalid item id)
        raise GaleAPIError(resp.status_code)

    def get_api_key(self):
        """Get a new API key to use for requests in the next 30 minutes."""
        # GALE API requires use of an API key, which lasts for 30 minutes
        # request a new one when needed using configured username
        response = self._make_request(
            "tools/generate_key", {"user": self.username}, requires_api_key=False
        )
        return response.json()["apiKey"]

    _api_key = None

    @property
    def api_key(self):
        """Property for current api key. Uses :meth:`get_api_key` to
        request a new one when needed."""
        if self._api_key is None:
            self._api_key = self.get_api_key()
        return self._api_key

    def refresh_api_key(self):
        """clear cached api key and request a new one"""
        self._api_key = None
        assert self.api_key  # populate new key through property

    def get_item(self, item_id):
        """Get the full record for a single item"""
        # full id looks like GALE|CW###### or GALE|CB#######
        # using streaming makes a *significant* difference in response time,
        # especially for larger results
        response = self._make_request("v1/item/GALE%%7C%s" % item_id, stream=True)
        if response:
            return response.json()


# MARC records needed for import and metadata are stored in a local pairtree.
# currently used for Gale/ECCO content


def get_marc_storage():
    """return pairtree storage for marc records"""
    return PairtreeStorageFactory().get_store(
        store_dir=settings.MARC_DATA, uri_base="info:local/"
    )


class MARCRecordNotFound(Exception):
    """record not found in local MARC record storage"""


def get_marc_record(item_id):
    """get a marc record from the pairtree storage by Gale item id"""
    start_time = time.time()
    try:
        marc_object = get_marc_storage().get_object(item_id)
        with marc_object.get_bytestream("marc.dat", streamable=True) as marcfile:
            reader = pymarc.MARCReader(marcfile, to_unicode=True)
            record = [rec for rec in reader][0]
            logger.debug(
                "Loaded MARC record for %s in %.5fs"
                % (item_id, time.time() - start_time)
            )
    except storage_exceptions.PartNotFoundException:
        raise MARCRecordNotFound(item_id)
    return record
