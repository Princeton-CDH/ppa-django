import json
import os.path

from django.conf import settings
from django.test import TestCase

from ppa.archive.hathi import HathiBibliographicRecord

FIXTURES_PATH = os.path.join(settings.BASE_DIR, 'ppa', 'archive', 'fixtures')

class TestHathiBibliographicRecord(TestCase):
    bibdata_fixture = os.path.join(FIXTURES_PATH,
        'bibdata_full_njp.32101013082597.json')

    def setUp(self):
        with open(self.bibdata_fixture) as bibdata:
            self.record = HathiBibliographicRecord(json.load(bibdata))

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


