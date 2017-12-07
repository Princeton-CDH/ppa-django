from datetime import date
import json
import os.path
from unittest.mock import patch, Mock

from django.conf import settings
from django.test import TestCase, override_settings
import pymarc
import requests
from SolrClient import SolrClient

from ppa.archive.hathi import HathiBibliographicRecord
from ppa.archive.models import DigitizedWork
from ppa.archive.solr import get_solr_connection, SolrSchema, CoreAdmin


FIXTURES_PATH = os.path.join(settings.BASE_DIR, 'ppa', 'archive', 'fixtures')


class TestHathiBibliographicRecord(TestCase):
    bibdata_full = os.path.join(FIXTURES_PATH,
        'bibdata_full_njp.32101013082597.json')
    bibdata_brief = os.path.join(FIXTURES_PATH,
        'bibdata_brief_njp.32101013082597.json')

    def setUp(self):
        with open(self.bibdata_full) as bibdata:
            self.record = HathiBibliographicRecord(json.load(bibdata))

        with open(self.bibdata_brief) as bibdata:
            self.brief_record = HathiBibliographicRecord(json.load(bibdata))

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


TEST_SOLR_CONNECTIONS = {
    'default': {
        'COLLECTION': 'testppa',
        'URL': 'http://example.com:8984/solr/',
        'ADMIN_URL': 'http://example.com:8984/solr/admin/cores'
    }
}

@override_settings(SOLR_CONNECTIONS=TEST_SOLR_CONNECTIONS)
def test_get_solr_connection():
    # test basic solr connection setup
    solr, collection = get_solr_connection()
    assert isinstance(solr, SolrClient)
    assert solr.host == TEST_SOLR_CONNECTIONS['default']['URL']
    assert collection == TEST_SOLR_CONNECTIONS['default']['COLLECTION']

    # TODO: test error handling once we have some


@override_settings(SOLR_CONNECTIONS=TEST_SOLR_CONNECTIONS)
@patch('ppa.archive.solr.get_solr_connection')
class TestSolrSchema(TestCase):

    def test_solr_schema_fields(self, mock_get_solr_connection):
        mocksolr = Mock()
        mock_get_solr_connection.return_value = (mocksolr, 'testcoll')
        mocksolr.schema.get_schema_fields.return_value = {
            'fields': [
                {'name': 'author', 'type': 'text_en', 'required': False},
                {'name': 'title', 'type': 'text_en', 'required': False},
                {'name': 'date', 'type': 'int', 'required': False},
            ]
        }
        schema = SolrSchema()
        fields = schema.solr_schema_fields()
        for expected_field in ['author', 'title', 'date']:
            assert expected_field in fields

    def test_update_solr_schema(self, mock_get_solr_connection):
        mocksolr = Mock()
        coll = 'testcoll'
        mock_get_solr_connection.return_value = (mocksolr, coll)
        # simulate no fields in solr
        mocksolr.schema.get_schema_fields.return_value = {'fields': []}
        test_copy_field = {'source': 'id', 'dest': 'text'}
        mocksolr.schema.get_schema_copyfields.return_value = [
            test_copy_field
        ]

        schema = SolrSchema()
        schema.fields = [
            {'name': 'author', 'type': 'text_en', 'required': False},
            {'name': 'title', 'type': 'text_en', 'required': False},
            {'name': 'pub_date', 'type': 'int', 'required': False},
        ]

        created, updated, removed = schema.update_solr_schema()
        assert created == 3
        assert updated == 0
        assert removed == 0
        for field_def in schema.fields:
            mocksolr.schema.create_field.assert_any_call(coll, field_def)

        mocksolr.schema.replace_field.assert_not_called()
        mocksolr.schema.delete_field.assert_not_called()
        mocksolr.schema.delete_copy_field.assert_called_with(coll, test_copy_field)

        # simulate all fields in solr
        mocksolr.schema.get_schema_fields.return_value = {'fields': schema.fields}
        mocksolr.schema.create_field.reset_mock()

        created, updated, removed = schema.update_solr_schema()
        assert created == 0
        assert updated == 3
        assert removed == 0
        mocksolr.schema.create_field.assert_not_called()
        for field_def in schema.fields:
            mocksolr.schema.replace_field.assert_any_call(coll, field_def)
        mocksolr.schema.delete_field.assert_not_called()

        # remove outdated fields
        mocksolr.schema.get_schema_fields.return_value = {'fields':
            schema.fields + [
            {'name': '_root_'},
            {'name': '_text_'},
            {'name': '_version_'},
            {'name': 'id'},
            {'name': 'oldfield'},
        ]}
        mocksolr.schema.create_field.reset_mock()
        mocksolr.schema.replace_field.reset_mock()
        created, updated, removed = schema.update_solr_schema()
        assert created == 0
        assert updated == 3
        assert removed == 1
        mocksolr.schema.delete_field.assert_called_once_with(coll, 'oldfield')


@override_settings(SOLR_CONNECTIONS=TEST_SOLR_CONNECTIONS)
class TestCoreAdmin(TestCase):

    def test_init(self):
        core_adm = CoreAdmin()
        assert core_adm.admin_url == settings.SOLR_CONNECTIONS['default']['ADMIN_URL']

    @patch('ppa.archive.solr.requests')
    def test_reload(self, mockrequests):
        # simulate success
        mockrequests.codes = requests.codes
        mockrequests.get.return_value.status_code = requests.codes.ok
        core_adm = CoreAdmin()
        # should return true for success
        assert core_adm.reload()
        # should call with configured collection
        mockrequests.get.assert_called_with(core_adm.admin_url,
            params={'action': 'RELOAD',
                    'core': settings.SOLR_CONNECTIONS['default']['COLLECTION']})

        # reload specific core
        assert core_adm.reload('othercore')
        mockrequests.get.assert_called_with(core_adm.admin_url,
            params={'action': 'RELOAD',
                    'core': 'othercore'})

        # failure
        mockrequests.get.return_value.status_code = requests.codes.not_found
        assert not core_adm.reload('othercore')


class TestDigitizedWork(TestCase):

    def test_populate_from_bibdata(self):
        with open(TestHathiBibliographicRecord.bibdata_full) as bibdata:
            full_bibdata = HathiBibliographicRecord(json.load(bibdata))

        with open(TestHathiBibliographicRecord.bibdata_brief) as bibdata:
            brief_bibdata = HathiBibliographicRecord(json.load(bibdata))

        digwork = DigitizedWork(source_id='njp.32101013082597')
        digwork.populate_from_bibdata(brief_bibdata)
        assert digwork.title == brief_bibdata.title
        assert digwork.pub_date == brief_bibdata.pub_dates[0]
        # no enumcron in this record
        assert digwork.enumcron == ''
        # fields from marc not set
        assert not digwork.author
        assert not digwork.pub_place
        assert not digwork.publisher

        # test no pub date
        brief_bibdata.info['publishDates'] = []
        digwork = DigitizedWork(source_id='njp.32101013082597')
        digwork.populate_from_bibdata(brief_bibdata)
        assert not digwork.pub_date

        # TODO: test enumcron from copy details

        # populate from full record
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.author == full_bibdata.marcxml.author()
        assert digwork.pub_place == full_bibdata.marcxml['260']['a']
        assert digwork.publisher == full_bibdata.marcxml['260']['b']

        # TODO: test publication info unavailable?

    def test_index_data(self):
        digwork = DigitizedWork(source_id='njp.32101013082597',
            title='Structure of English Verse', pub_date=1884,
            author='Charles Witcomb', pub_place='Paris',
            publisher='Mesnil-Dramard',
            source_url='https://hdl.handle.net/2027/njp.32101013082597')
        index_data = digwork.index_data()
        assert index_data['id'] == digwork.source_id
        assert index_data['srcid'] == digwork.source_id
        assert index_data['item_type'] == 'work'
        assert index_data['title'] == digwork.title
        assert index_data['author'] == digwork.author
        assert index_data['pub_place'] == digwork.pub_place
        assert index_data['pub_date'] == digwork.pub_date
        assert index_data['publisher'] == digwork.publisher
        assert index_data['src_url'] == digwork.source_url
        assert not index_data['enumcron']

        # with enumcron
        digwork.enumcron = 'v.7 (1848)'
        assert digwork.index_data()['enumcron'] == digwork.enumcron


