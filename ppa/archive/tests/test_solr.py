import pytest

from unittest.mock import patch, Mock

from django.conf import settings
from django.test import TestCase, override_settings
import requests
from SolrClient import SolrClient

from ppa.archive.solr import get_solr_connection, SolrSchema, CoreAdmin, \
    PagedSolrQuery


TEST_SOLR_CONNECTIONS = {
    'default': {
        'COLLECTION': 'testppa',
        'URL': 'http://localhost:191918984/solr/',
        'ADMIN_URL': 'http://localhost:191918984/solr/admin/cores'
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

@patch('ppa.archive.solr.get_solr_connection')
class TestPagedSolrQuery(TestCase):

    def test_init(self, mock_get_solr_connection):
        mocksolr = Mock()
        coll = 'testcoll'
        mock_get_solr_connection.return_value = (mocksolr, coll)

        psq = PagedSolrQuery()
        assert psq.solr == mocksolr
        assert psq.solr_collection == coll
        assert psq.query_opts == {}

        opts = {'q': '*:*'}
        psq = PagedSolrQuery(query_opts=opts)
        assert psq.query_opts == opts

    def test_add_facet(self, mock_get_solr_connection):
        mocksolr = Mock()
        coll = 'testcoll'
        mock_get_solr_connection.return_value = (mocksolr, coll)
        psq = PagedSolrQuery()
        assert 'facet' not in psq.query_opts
        # add a facet, should have facet set to true and a facet field
        psq.add_facet('foo')
        assert psq.query_opts['facet'] == 'true'
        assert psq.query_opts['facet.field'] == ['foo']
        # add another, facet.field should now be a list of two
        psq.add_facet('bar')
        assert psq.query_opts['facet.field'] == ['foo', 'bar']

    def test_get_facets(self, mock_get_solr_connection):
        mocksolr = Mock()
        coll = 'testcoll'
        mock_get_solr_connection.return_value = (mocksolr, coll)
        psq = PagedSolrQuery()
        # no result
        assert psq._result is None
        psq.get_facets()
        # result should be set by calling get_results()
        assert psq._result
        # mocksolr's get_facets should have been called
        assert psq._result.get_facets.called

    def test_get_results(self, mock_get_solr_connection):
        mocksolr = Mock()
        coll = 'testcoll'
        mock_get_solr_connection.return_value = (mocksolr, coll)
        psq = PagedSolrQuery()
        results = psq.get_results()
        mocksolr.query.assert_called_once_with(coll, psq.query_opts)
        assert results == mocksolr.query.return_value.docs

    def test_count(self, mock_get_solr_connection):
        mocksolr = Mock()
        coll = 'testcoll'
        mock_get_solr_connection.return_value = (mocksolr, coll)
        mocksolr.query.return_value.get_num_found.return_value = 42
        psq = PagedSolrQuery()
        assert psq.count() == 42

    def test_get_json(self, mock_get_solr_connection):
        mocksolr = Mock()
        coll = 'testcoll'
        mock_get_solr_connection.return_value = (mocksolr, coll)
        mocksolr.query.return_value.get_num_found.return_value = 42
        psq = PagedSolrQuery()
        assert psq.get_json() == mocksolr.query.return_value.get_json.return_value

    def test_set_limits(self, mock_get_solr_connection):
        mock_get_solr_connection.return_value = (Mock(), 'coll')
        psq = PagedSolrQuery()
        psq.set_limits(1, 10)
        assert psq.query_opts['start'] == 1
        assert psq.query_opts['rows'] == 10
        psq.set_limits(100, 120)
        assert psq.query_opts['start'] == 100
        assert psq.query_opts['rows'] == 21

    def test_slice(self, mock_get_solr_connection):
        mocksolr = Mock()
        mock_get_solr_connection.return_value = (mocksolr, 'coll')

        psq = PagedSolrQuery()
        with patch.object(psq, 'set_limits') as mock_set_limits:
            # slice
            psq[:10]
            mock_set_limits.assert_any_call(None, 10)
            psq[4:10]
            mock_set_limits.assert_any_call(4, 10)
            psq[20:]
            mock_set_limits.assert_any_call(20, None)

            with patch.object(psq, 'get_results') as mock_get_results:
                mock_get_results.return_value = [3,]
                assert psq[0] == 3
                mock_set_limits.assert_any_call(0, 1)
