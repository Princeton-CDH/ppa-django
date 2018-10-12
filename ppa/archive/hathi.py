'''
Utilities for working with HathiTrust materials and APIs.
'''
from datetime import datetime
import logging
import io
import time

from eulxml import xmlmap
import pymarc
import requests
from cached_property import cached_property

from ppa import __version__ as ppa_version


logger = logging.getLogger(__name__)


class HathiItemNotFound(Exception):
    '''Item not found in bibliographic API'''
    pass


class HathiBibliographicAPI(object):
    '''Wrapper for HathiTrust Bibliographic API.

    https://www.hathitrust.org/bib_api
    '''

    api_root = 'http://catalog.hathitrust.org/api'

    def __init__(self):
        # create a request session, for request pooling
        self.session = requests.Session()
        # set a user-agent header, but  preserve requests version information
        self.session.headers.update({
            'User-Agent': 'ppa-django/%s (%s)' % \
                (ppa_version, self.session.headers['User-Agent'])
        })
        # NOTE: we should probably set a From header based on a
        # technical contact email address configurable local settings...

    def _get_record(self, mode, id_type, id_value):
        url = '%(base)s/volumes/%(mode)s/%(id_type)s/%(id_value)s.json' % {
            'base': self.api_root,
            'mode': mode,
            'id_type': id_type,
            'id_value': id_value # NOTE: / in ark ids is *not* escaped
        }
        start = time.time()
        resp = self.session.get(url)
        logger.debug('get record %s/%s %s: %f sec', id_type, id_value,
                     resp.status_code, time.time() - start)
        # TODO: handle errors
        if resp.status_code == requests.codes.ok:
            # for an invalid id, hathi seems to return a 200 ok
            # but json has no records
            if not resp.json().get('records', None):
                raise HathiItemNotFound
            return HathiBibliographicRecord(resp.json())

    def brief_record(self, id_type, id_value):
        '''Get brief record by id type and value.

        :returns: :class:`HathiBibliographicRecord`
        :raises: :class:`HathiItemNotFound`
        '''
        return self._get_record('brief', id_type, id_value)

    def record(self, id_type, id_value):
        '''Get full record by id type and value.

        :returns: :class:`HathiBibliographicRecord`
        :raises: :class:`HathiItemNotFound`
        '''
        return self._get_record('full', id_type, id_value)

    # also possible: get multiple records at once


class HathiBibliographicRecord(object):
    '''Representation of a HathiTrust bibliographic record.'''
    def __init__(self, data):
        self._data = data
        # for a single bib api json result, we only want the first item
        self.record_id = list(data['records'].keys())[0]
        self.info = list(data['records'].values())[0]

    @property
    def title(self):
        '''First title (standard title)'''
        # returns list of titles - standard title; could also have
        # title without leading article and other language titles
        return self.info['titles'][0]

    @property
    def pub_dates(self):
        ''' list of available publication dates'''
        return self.info['publishDates']

    def copy_details(self, htid):
        '''Details for a specific copy identified by hathi id'''
        for item in self._data['items']:
            if item['htid'] == htid:
                return item

    def copy_last_updated(self, htid):
        '''Return last update date for a specificy copy identified by
        hathi id.  Returns as :class:`datetime.date`'''
        # get last update from copy details
        last_update = self.copy_details(htid)['lastUpdate']
        # use datetime to parse, then return just thed ate
        return datetime.strptime(last_update, '%Y%m%d').date()

    @cached_property
    def marcxml(self):
        '''Record marcxml if included (full records only), as an instance of
        :class:`pymarc.Record`'''
        marcxml = self._data['records'][self.record_id].get('marc-xml', None)
        if marcxml:
            return pymarc.parse_xml_to_array(io.StringIO(marcxml))[0]


class _METS(xmlmap.XmlObject):
    '''Base :class:`~eulxml.xmlmap.XmlObject`. with METS namespace configured'''
    ROOT_NAMESPACES = {
        'm': 'http://www.loc.gov/METS/'
    }

class StructMapPage(_METS):
    '''Single logical page within a METS StructMap'''
    #: page order
    order = xmlmap.IntegerField('@ORDER')
    #: page label
    label = xmlmap.StringField('@LABEL')
    #: order label
    orderlabel = xmlmap.StringField('@ORDERLABEL')
    #: identifier for a text or ocr file, from a file pointer
    text_file_id = xmlmap.StringField('m:fptr/@FILEID[contains(., "TXT") or contains(. , "OCR")]')

    ## example struct map page
    '''<METS:div ORDER="1" LABEL="FRONT_COVER, IMAGE_ON_PAGE, IMPLICIT_PAGE_NUMBER" TYPE="page">
         <METS:fptr FILEID="HTML00000001"/>
         <METS:fptr FILEID="TXT00000001"/>
         <METS:fptr FILEID="IMG00000001"/>
       <METS:file SIZE="1003" ID="HTML00000496" MIMETYPE="text/html" CREATED="2017-03-20T10:40:21Z"
         CHECKSUM="f0a326c10b2a6dc9ae5e3ede261c9897" SEQ="00000496" CHECKSUMTYPE="MD5">
    '''

    @property
    def display_label(self):
        '''page display labeel; use order label if present; otherwise use order'''
        return self.orderlabel or str(self.order)

    @property
    def text_file(self):
        ''':class:`METSFiile` corresponding to the text file pointer for this page'''
        return METSFile(self.node.xpath('//m:file[@ID="%s"]' % self.text_file_id,
                                        namespaces=self.ROOT_NAMESPACES)[0])
    @property
    def text_file_location(self):
        '''location for the text file'''
        return self.text_file.location


class METSFile(_METS):
    '''File location information within a METS document.'''
    #: xml identifier
    id = xmlmap.StringField('@ID')
    #: sequence attribute
    sequence = xmlmap.StringField('@SEQ')
    #: file location
    location = xmlmap.StringField('m:FLocat/@xlink:href')
    # example file
    '''<METS:file SIZE="1" ID="TXT00000001" MIMETYPE="text/plain"
        CREATED="2016-06-24T09:04:15Z" CHECKSUM="68b329da9893e34099c7d8ad5cb9c940"
        SEQ="00000001" CHECKSUMTYPE="MD5">
    '''

class MinimalMETS(_METS):
    '''Minimal :class:`~eulxml.xmlmap.XmlObject` for METS that maps only
    what is needed to support page indexing for :mod:`ppa`.'''

    #: list of struct map pages as :class:`StructMapPage`
    structmap_pages = xmlmap.NodeListField('m:structMap[@TYPE="physical"]//m:div[@TYPE="page"]',
                                           StructMapPage)
