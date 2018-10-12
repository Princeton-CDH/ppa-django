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


logger = logging.getLogger(__name__)


class HathiItemNotFound(Exception):
    '''Item not found in bibliographic API'''
    pass


class HathiBibliographicAPI(object):
    '''Wrapper for HathiTrust Bibliographic API.

    https://www.hathitrust.org/bib_api
    '''

    api_root = 'http://catalog.hathitrust.org/api'

    def _get_record(self, mode, id_type, id_value):
        url = '%(base)s/volumes/%(mode)s/%(id_type)s/%(id_value)s.json' % {
            'base': self.api_root,
            'mode': mode,
            'id_type': id_type,
            'id_value': id_value # NOTE: / in ark ids is *not* escaped
        }
        start = time.time()
        resp = requests.get(url)
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

    ROOT_NAMESPACES = {
        'm': 'http://www.loc.gov/METS/'
    }

class StructMapPage(_METS):
    order = xmlmap.StringField('@ORDER')
    label = xmlmap.StringField('@LABEL')
    orderlabel = xmlmap.StringField('@ORDERLABEL')
    text_file_id = xmlmap.StringField('m:fptr/@FILEID[contains(., "TXT") or contains(. , "OCR")]')

    @property
    def display_label(self):
        return self.orderlabel or self.label

    @property
    def text_file(self):
        return METSFile(self.node.xpath('//m:file[@ID="%s"]' % self.text_file_id,
                                        namespaces=self.ROOT_NAMESPACES)[0])
    @property
    def text_file_location(self):
        return self.text_file.location

      # <METS:div ORDER="1" LABEL="FRONT_COVER, IMAGE_ON_PAGE, IMPLICIT_PAGE_NUMBER" TYPE="page">
      #   <METS:fptr FILEID="HTML00000001"/>
      #   <METS:fptr FILEID="TXT00000001"/>
      #   <METS:fptr FILEID="IMG00000001"/>
      # <METS:file SIZE="1003" ID="HTML00000496" MIMETYPE="text/html" CREATED="2017-03-20T10:40:21Z" CHECKSUM="f0a326c10b2a6dc9ae5e3ede261c9897" SEQ="00000496" CHECKSUMTYPE="MD5">

class METSFile(_METS):
    id = xmlmap.StringField('@ID')
    sequence = xmlmap.StringField('@SEQ')
    location = xmlmap.StringField('m:FLocat/@xlink:href')

class MinimalMETS(_METS):
    structmap_pages = xmlmap.NodeListField('m:structMap[@TYPE="physical"]//m:div[@TYPE="page"]',
        StructMapPage)
    ocr_files = xmlmap.NodeListField('m:fileGrp[@USE="ocr"]/m:file', METSFile)

    def file_by_id(self, file_id):
        return METSFile(self.node.xpath('//m:file[@ID="%s"]' % file_id,
                                        namespaces=self.ROOT_NAMESPACES)[0])



