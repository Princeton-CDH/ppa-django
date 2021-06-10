import logging

import requests

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from ppa import __version__ as ppa_version


logger = logging.getLogger(__name__)


class GaleAPIError(Exception):
    """Base exception class for Gale API errors"""


class GaleItemForbidden(GaleAPIError):
    """Permission denied to access item in Gale API"""


class GaleItemNotFound(GaleAPIError):
    """Item not found in Gale API"""


class GaleAPI:

    #: base URL for all API requests
    api_root = "https://api.gale.com/api"

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

    def _make_request(self, url, params=None, requires_api_key=True, stream=False):
        """Make a GET request with the configured session. Takes a url
        relative to :attr:`api_root` and optional dictionary of parameters."""
        # NOTE: also copied from hathi.py

        # Returns the response for status 200 OK; raises
        # :class:`HathiItemNotFound` for 404 and :class:`HathiItemForbidden`
        # for 403.
        # '''
        url = "%s/%s" % (self.api_root, url)
        rqst_opts = {}
        if params:
            rqst_opts["params"] = params

        # add api key to parameters if neded for this request
        if requires_api_key:
            if "params" not in rqst_opts:
                rqst_opts["params"] = {}
            rqst_opts["params"]["api_key"] = self.api_key

        resp = self.session.get(url, stream=stream, **rqst_opts)
        logger.debug(
            "get %s %s: %f sec", url, resp.status_code, resp.elapsed.total_seconds()
        )
        if resp.status_code == requests.codes.ok:
            return resp
        if resp.status_code == requests.codes.not_found:
            raise GaleItemNotFound

        # TODO: handle 401 / requests.codes.unauthorized
        # HTTP Status 401 - Authentication Failed: Invalid or Expired API key

        if resp.status_code == requests.codes.forbidden:
            # forbidden results return a message
            # NOTE that item requests for invalid ids return 403
            # TODO: add logic to check if api key has expired and get a new one?
            # (if we expect to ever have anything that will take longer than 30m)
            raise GaleItemForbidden(resp.json()["message"])

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

    def get_item(self, item_id):
        """Get the full record for a single item"""
        # full id looks like GALE|CW###### or GAlE|CB#######
        # using streaming makes a *significant* difference in response time,
        # especially for larger results
        response = self._make_request(f"v1/item/GALE%7C{item_id}", stream=True)
        if response:
            return response.json()