from datetime import date
import os.path
from unittest.mock import patch
import json

from django.conf import settings
from django.test import TestCase
from eulxml.xmlmap import load_xmlobject_from_file
import pymarc
import pytest
import requests

from ppa.archive import hathi


FIXTURES_PATH = os.path.join(settings.BASE_DIR, 'ppa', 'archive', 'fixtures')


@patch('ppa.archive.hathi.requests')
class TestHathiBibliographicAPI(TestCase):
    bibdata = os.path.join(FIXTURES_PATH,
        'bibdata_brief_njp.32101013082597.json')

    def test_brief_record(self, mockrequests):
        mockrequests.codes = requests.codes
        mocksession = mockrequests.Session.return_value
        mocksession.get.return_value.status_code = requests.codes.ok

        bib_api = hathi.HathiBibliographicAPI()
        htid = 'njp.32101013082597'

        # no result found
        mocksession.get.return_value.json.return_value = {}
        with pytest.raises(hathi.HathiItemNotFound):
            bib_api.brief_record('htid', htid)

        # use fixture to simulate result found
        with open(self.bibdata) as sample_bibdata:
            mocksession.get.return_value.json.return_value = json.load(sample_bibdata)

        record = bib_api.brief_record('htid', htid)
        assert isinstance(record, hathi.HathiBibliographicRecord)

        # check expected url was called
        mocksession.get.assert_any_call(
            'http://catalog.hathitrust.org/api/volumes/brief/htid/%s.json' % htid)

        # ark ids are not escaped
        htid = 'aeu.ark:/13960/t1pg22p71'
        bib_api.brief_record('htid', htid)
        mocksession.get.assert_any_call(
            'http://catalog.hathitrust.org/api/volumes/brief/htid/%s.json' % htid)

        # alternate id
        oclc_id = '424023'
        bib_api.brief_record('oclc', oclc_id)
        mocksession.get.assert_any_call(
            'http://catalog.hathitrust.org/api/volumes/brief/oclc/%s.json' % oclc_id)

    def test_record(self, mockrequests):
        mockrequests.codes = requests.codes
        mocksession = mockrequests.Session.return_value
        mocksession.get.return_value.status_code = requests.codes.ok

        bib_api = hathi.HathiBibliographicAPI()
        htid = 'njp.32101013082597'

        # use fixture to simulate result found
        with open(self.bibdata) as sample_bibdata:
            mocksession.get.return_value.json.return_value = json.load(sample_bibdata)

        record = bib_api.record('htid', htid)
        assert isinstance(record, hathi.HathiBibliographicRecord)

        # check expected url was called - full instead of brief
        mocksession.get.assert_any_call(
            'http://catalog.hathitrust.org/api/volumes/full/htid/%s.json' % htid)


class TestHathiBibliographicRecord(TestCase):
    bibdata_full = os.path.join(FIXTURES_PATH,
        'bibdata_full_njp.32101013082597.json')
    bibdata_brief = os.path.join(FIXTURES_PATH,
        'bibdata_brief_njp.32101013082597.json')

    def setUp(self):
        with open(self.bibdata_full) as bibdata:
            self.record = hathi.HathiBibliographicRecord(json.load(bibdata))

        with open(self.bibdata_brief) as bibdata:
            self.brief_record = hathi.HathiBibliographicRecord(json.load(bibdata))

    def test_properties(self):
        record = self.record
        assert record.record_id == '008883512'
        assert record.title == \
            "Lectures on the literature of the age of Elizabeth, and Characters of Shakespear's plays,"
        assert record.pub_dates == ['1882']
        copy_details = record.copy_details('njp.32101013082597')
        assert isinstance(copy_details, dict)
        assert copy_details['orig'] == 'Princeton University'

        assert record.copy_details('bogus') is None

        # brief record should work the same way
        record = self.brief_record
        assert record.record_id == '008883512'
        assert record.title == \
            "Lectures on the literature of the age of Elizabeth, and Characters of Shakespear's plays,"
        assert record.pub_dates == ['1882']
        copy_details = record.copy_details('njp.32101013082597')
        assert isinstance(copy_details, dict)
        assert copy_details['orig'] == 'Princeton University'

        assert record.copy_details('bogus') is None

    def test_copy_last_updated(self):
        update_date = self.record.copy_last_updated('njp.32101013082597')
        assert isinstance(update_date, date)
        assert update_date == date(2017, 3, 24)

    def test_marcxml(self):
        record = self.record
        assert isinstance(record.marcxml, pymarc.Record)
        assert record.marcxml.author() == 'Hazlitt, William, 1778-1830.'

        # test no marcxml in data, e.g. brief record
        assert self.brief_record.marcxml is None


class TestMETS(TestCase):
    metsfile = os.path.join(FIXTURES_PATH, '79279237.mets.xml')

    def setUp(self):
        self.mets = load_xmlobject_from_file(self.metsfile, hathi.MinimalMETS)

    def test_init_minimal_mets(self):
        assert isinstance(self.mets.structmap_pages[0], hathi.StructMapPage)
        assert len(self.mets.structmap_pages) == 640

    def test_structmap(self):
        page = self.mets.structmap_pages[0]
        assert page.order == 1
        assert page.label == 'FRONT_COVER, IMAGE_ON_PAGE, IMPLICIT_PAGE_NUMBER'
        assert not page.orderlabel
        assert page.text_file_id == 'TXT00000001'
        # page 1 has no order label
        assert page.display_label == '1'
        assert isinstance(page.text_file, hathi.METSFile)
        assert page.text_file_location == '00000001.txt'

        # pages with order label start at order 15
        page = self.mets.structmap_pages[14]
        assert page.orderlabel == '1'
        assert page.display_label == page.orderlabel

    def test_metsfile(self):
        page = self.mets.structmap_pages[0]
        textfile = page.text_file
        assert textfile.id == page.text_file_id
        assert textfile.sequence == '00000001'
        assert textfile.location == '00000001.txt'
