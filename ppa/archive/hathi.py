"""
Utilities for working with HathiTrust materials and APIs.
"""
import io
import logging
import os.path
import time
from datetime import datetime
from zipfile import ZipFile

import pymarc
import requests
from cached_property import cached_property
from django.conf import settings
from neuxml import xmlmap
from pairtree import pairtree_client, pairtree_path, storage_exceptions

from ppa import __version__ as ppa_version

logger = logging.getLogger(__name__)


class HathiItemNotFound(Exception):
    """Item not found in bibliographic or data API"""

    pass


class HathiItemForbidden(Exception):
    """Permission denied to access item in data API"""

    pass


class HathiBaseAPI:
    """Base client class for HathiTrust APIs"""

    #: base api URL for all requests
    api_root = ""

    def __init__(self):
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

    def __del__(self):
        # close the request session
        self.session.close()

    def _make_request(self, url, params=None):
        """Make a GET request with the configured session. Takes a url
        relative to :attr:`api_root` and optional dictionary of parameters.
        Returns the response for status 200 OK; raises
        :class:`HathiItemNotFound` for 404 and :class:`HathiItemForbidden`
        for 403.
        """
        url = "%s/%s" % (self.api_root, url)
        rqst_opts = {}
        if params:
            rqst_opts["params"] = params

        start = time.time()
        resp = self.session.get(url, **rqst_opts)
        logger.debug("get %s %s: %f sec", url, resp.status_code, time.time() - start)
        if resp.status_code == requests.codes.ok:
            return resp
        if resp.status_code == requests.codes.not_found:
            raise HathiItemNotFound
        if resp.status_code == requests.codes.forbidden:
            raise HathiItemForbidden


class HathiBibliographicAPI(HathiBaseAPI):
    """Wrapper for HathiTrust Bibliographic API.

    https://www.hathitrust.org/bib_api
    """

    api_root = "http://catalog.hathitrust.org/api"

    def _get_record(self, mode, id_type, id_value):
        url = "volumes/%(mode)s/%(id_type)s/%(id_value)s.json" % {
            "mode": mode,
            "id_type": id_type,
            "id_value": id_value,  # NOTE: / in ark ids is *not* escaped
        }
        resp = self._make_request(url)
        # for an invalid id, hathi seems to return a 200 ok
        # but json has no records
        if not resp.json().get("records", None):
            raise HathiItemNotFound
        return HathiBibliographicRecord(resp.json())

    def brief_record(self, id_type, id_value):
        """Get brief record by id type and value.

        :returns: :class:`HathiBibliographicRecord`
        :raises: :class:`HathiItemNotFound`
        """
        return self._get_record("brief", id_type, id_value)

    def record(self, id_type, id_value):
        """Get full record by id type and value.

        :returns: :class:`HathiBibliographicRecord`
        :raises: :class:`HathiItemNotFound`
        """
        return self._get_record("full", id_type, id_value)

    # also possible: get multiple records at once


class HathiBibliographicRecord:
    """Representation of a HathiTrust bibliographic record."""

    def __init__(self, data):
        self._data = data
        # for a single bib api json result, we only want the first item
        self.record_id = list(data["records"].keys())[0]
        self.info = list(data["records"].values())[0]

    @property
    def title(self):
        """First title (standard title)"""
        # returns list of titles - standard title; could also have
        # title without leading article and other language titles
        return self.info["titles"][0]

    @property
    def pub_dates(self):
        """list of available publication dates"""
        return self.info["publishDates"]

    def copy_details(self, htid):
        """Details for a specific copy identified by hathi id"""
        for item in self._data["items"]:
            if item["htid"] == htid:
                return item

    def copy_last_updated(self, htid):
        """Return last update date for a specificy copy identified by
        hathi id.  Returns as :class:`datetime.date`"""
        # get last update from copy details
        last_update = self.copy_details(htid)["lastUpdate"]
        # use datetime to parse, then return just thed ate
        return datetime.strptime(last_update, "%Y%m%d").date()

    @cached_property
    def marcxml(self):
        """Record marcxml if included (full records only), as an instance of
        :class:`pymarc.Record`"""
        marcxml = self._data["records"][self.record_id].get("marc-xml", None)
        if marcxml:
            return pymarc.parse_xml_to_array(io.StringIO(marcxml))[0]


class _METS(xmlmap.XmlObject):
    """Base :class:`~neuxml.xmlmap.XmlObject`. with METS namespace configured"""

    ROOT_NAMESPACES = {"m": "http://www.loc.gov/METS/"}


class StructMapPage(_METS):
    """Single logical page within a METS StructMap"""

    #: page order
    order = xmlmap.IntegerField("@ORDER")
    #: page label
    label = xmlmap.StringField("@LABEL")
    #: order label
    orderlabel = xmlmap.StringField("@ORDERLABEL")
    #: identifier for a text or ocr file, from a file pointer
    text_file_id = xmlmap.StringField(
        'm:fptr/@FILEID[contains(., "TXT") or contains(. , "OCR")]'
    )

    ## example struct map page
    """<METS:div ORDER="1" LABEL="FRONT_COVER, IMAGE_ON_PAGE, IMPLICIT_PAGE_NUMBER" TYPE="page">
         <METS:fptr FILEID="HTML00000001"/>
         <METS:fptr FILEID="TXT00000001"/>
         <METS:fptr FILEID="IMG00000001"/>
       <METS:file SIZE="1003" ID="HTML00000496" MIMETYPE="text/html" CREATED="2017-03-20T10:40:21Z"
         CHECKSUM="f0a326c10b2a6dc9ae5e3ede261c9897" SEQ="00000496" CHECKSUMTYPE="MD5">
    """  # noqa: E501

    @cached_property
    def display_label(self):
        """page display labeel; use order label if present; otherwise use order"""
        return self.orderlabel or str(self.order)

    @cached_property
    def text_file(self):
        """:class:`METSFiile` corresponding to the text file pointer for this page"""
        return METSFile(
            self.node.xpath(
                '//m:file[@ID="%s"]' % self.text_file_id,
                namespaces=self.ROOT_NAMESPACES,
            )[0]
        )

    @cached_property
    def text_file_location(self):
        """location for the text file"""
        return self.text_file.location


class METSFile(_METS):
    """File location information within a METS document."""

    #: xml identifier
    id = xmlmap.StringField("@ID")
    #: sequence attribute
    sequence = xmlmap.StringField("@SEQ")
    #: file location
    location = xmlmap.StringField("m:FLocat/@xlink:href")
    # example file
    """<METS:file SIZE="1" ID="TXT00000001" MIMETYPE="text/plain"
        CREATED="2016-06-24T09:04:15Z" CHECKSUM="68b329da9893e34099c7d8ad5cb9c940"
        SEQ="00000001" CHECKSUMTYPE="MD5">
    """


class MinimalMETS(_METS):
    """Minimal :class:`~neuxml.xmlmap.XmlObject` for METS that maps only
    what is needed to support page indexing for :mod:`ppa`."""

    #: list of struct map pages as :class:`StructMapPage`
    structmap_pages = xmlmap.NodeListField(
        'm:structMap[@TYPE="physical"]//m:div[@TYPE="page"]', StructMapPage
    )


class HathiObject:
    """An object for working with a HathiTrust item with data in a
    locally configured pairtree datastore."""

    # Pairtree version statement usd by pairtree package
    pairtree_version_stmt = (
        "This directory conforms to Pairtree Version 0.1. Updated spec: "
        + "http://www.cdlib.org/inside/diglib/pairtree/pairtreespec.html"
    )

    def __init__(self, hathi_id):
        # HathiTrust record id
        self.hathi_id = hathi_id
        # Identifiers for owning institution and volume which form the overall
        # HathiTrust record id: [lib_id].[vol_id]
        self.lib_id, self.vol_id = hathi_id.split(".", 1)
        # Pairtree prefix
        self.pairtree_prefix = f"{self.lib_id}."
        # Content directory for this work within the appropriate pairtree
        # which is based on a pairtree encoded version of the volume id
        self.content_dir = pairtree_path.id_encode(self.vol_id)

    def pairtree_client(self):
        """Initialize a pairtree client for the pairtree datastore this
        object belongs to, based on its HathiTrust record id."""
        store_dir = os.path.join(settings.HATHI_DATA, self.lib_id)

        # Check if store_dir exists, check if pairtree files exist
        if os.path.isdir(store_dir):
            # Check if "pairtree_prefix" file exists. If not, create it.
            pairtree_prefix_fn = os.path.join(store_dir, "pairtree_prefix")
            if not os.path.isfile(pairtree_prefix_fn):
                with open(pairtree_prefix_fn, mode="w") as writer:
                    writer.write(self.pairtree_prefix)
            # Check if "pairtree_version0_1" file exists. If not, create it.
            # Note: Mimicking paitree packages behavior. File contents are not
            #       actually verified
            pairtree_vn_fn = os.path.join(store_dir, "pairtree_version0_1")
            if not os.path.isfile(pairtree_vn_fn):
                with open(pairtree_vn_fn, mode="w") as writer:
                    writer.write(self.pairtree_version_stmt)

        return pairtree_client.PairtreeStorageClient(
            self.pairtree_prefix,
            store_dir,
        )

    def pairtree_object(self, ptree_client=None, create=False):
        """get a pairtree object for this record

        :param ptree_client: optional
            :class:`pairtree_client.PairtreeStorageClient` if one has
            already been initialized, to avoid repeated initialization
            (currently used in hathi_import manage command)
        """
        if ptree_client is None:
            # get pairtree client if not passed in
            ptree_client = self.pairtree_client()

        # return the pairtree object for current work
        return ptree_client.get_object(self.vol_id, create_if_doesnt_exist=create)

    def delete_pairtree_data(self):
        """Delete pairtree object from the pairtree datastore."""
        logger.info("Deleting pairtree data for %s", self.hathi_id)
        try:
            self.pairtree_client().delete_object(self.vol_id)
        except storage_exceptions.ObjectNotFoundException:
            # data is already gone; warn, but not an error
            logger.warning(
                "Pairtree deletion failed; object not found %s", self.hathi_id
            )

    def _content_path(self, ext, ptree_client=None):
        """path to zipfile within the hathi contents for this work"""
        pairtree_obj = self.pairtree_object(ptree_client=ptree_client)
        # - expect a mets file and a zip file
        # NOTE: not yet making use of the metsfile
        # - don't rely on them being returned in the same order on every machine
        parts = pairtree_obj.list_parts(self.content_dir)
        # find the first zipfile in the list (should only be one)
        filepaths = [part for part in parts if part.endswith(ext)]
        if not filepaths:
            # An error has occurred -- there is no zip file here in parts
            raise storage_exceptions.PartNotFoundException
        return os.path.join(
            pairtree_obj.id_to_dirpath(), self.content_dir, filepaths[0]
        )

    def zipfile_path(self, ptree_client=None):
        """path to zipfile within the hathi contents for this work"""
        return self._content_path("zip", ptree_client=ptree_client)

    def metsfile_path(self, ptree_client=None):
        """path to mets xml file within the hathi contents for this work"""
        return self._content_path(".mets.xml", ptree_client=ptree_client)

    def mets_xml(self) -> MinimalMETS:
        """load METS xml file from pairtree and initialize as an instance
        of :class:`MinimalMETS`

        :rtype: :class:`MinimalMETS`
        :raises: :class:`storage_exceptions.ObjectNotFoundException` if the
            object is not found in pairtree storage
        :raises: :class:`storage_exceptions.PartNotFoundException` if the
            mets.xml flie is not found in pairtree storage for this object
        """
        return xmlmap.load_xmlobject_from_file(self.metsfile_path(), MinimalMETS)

    def page_data(self):
        """Return a generator of page content for this HathiTrust work
        based on pairtree and METS data, for indexing pages in Solr."""

        # load mets record to pull metadata about the images
        try:
            mmets = self.mets_xml()
        except storage_exceptions.ObjectNotFoundException:
            logger.error(f"Pairtree data for {self.hathi_id} not found")
            return

        # read zipfile contents in place, without unzipping
        try:
            zpath = self.zipfile_path()
        except storage_exceptions.PartNotFoundException:
            # missing file inside pairtree if this error occurs
            logging.error(f"Missing pairtree data for: {self.hathi_id}")
            return

        with ZipFile(zpath) as ht_zip:
            # yield a generator of index data for each page; iterate
            # over pages in METS structmap
            for i, page in enumerate(mmets.structmap_pages, 1):
                # zipfile spec uses / for path regardless of OS
                pagefilename = "/".join([self.content_dir, page.text_file_location])
                try:
                    with ht_zip.open(pagefilename) as pagefile:
                        try:
                            yield {
                                "page_id": page.text_file.sequence,
                                "content": pagefile.read().decode("utf-8"),
                                "order": page.order,
                                "label": page.display_label,
                                "tags": page.label.split(", ") if page.label else [],
                            }
                        except StopIteration:
                            return
                except KeyError:
                    # we know of one HathiTrust work (uc1.$b31619) where
                    # the METS references pages that are not present in the zip file;
                    # they are at the end of the document and don't have any
                    # page content, so log a warning but don't treat as an error
                    logger.warn(
                        "Indexing %s pages: "
                        + "%s referenced in METS but not found in zip file",
                        self.hathi_id,
                        pagefilename,
                    )
