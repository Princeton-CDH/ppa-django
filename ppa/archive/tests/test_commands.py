from io import StringIO
import os
import tempfile
import types
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
import pytest

from ppa.archive.solr import SolrSchema, CoreAdmin
from ppa.archive.management.commands import hathi_import


@pytest.fixture
def empty_solr():
    # pytest solr fixture; updates solr schema
    with override_settings(SOLR_CONNECTIONS={'default': settings.SOLR_CONNECTIONS['test']}):
        # reload core before and after to ensure field list is accurate
        CoreAdmin().reload()
        solr_schema = SolrSchema()
        cp_fields = solr_schema.solr.schema.get_schema_copyfields(solr_schema.solr_collection)
        current_fields = solr_schema.solr_schema_fields()

        for cp_field in cp_fields:
            solr_schema.solr.schema.delete_copy_field(solr_schema.solr_collection, cp_field)
        for field in current_fields:
            solr_schema.solr.schema.delete_field(solr_schema.solr_collection, field)
        CoreAdmin().reload()


@pytest.fixture
def solr():
    # pytest solr fixture; updates solr schema
    with override_settings(SOLR_CONNECTIONS={'default': settings.SOLR_CONNECTIONS['test']}):
        # reload core before and after to ensure field list is accurate
        CoreAdmin().reload()
        SolrSchema().update_solr_schema()
        CoreAdmin().reload()


class TestSolrSchemaCommand(TestCase):

    def test_connection_error(self):
        # simulate no solr running
        with override_settings(SOLR_CONNECTIONS={'default':
                              {'COLLECTION': 'bogus',
                               'URL': 'http://localhost:191918984/solr/'}}):
            with pytest.raises(CommandError):
                call_command('solr_schema')

    @pytest.mark.skip   # skip for now - causing an error on travis-ci
    @pytest.mark.usefixtures("empty_solr")
    def test_empty_solr(self):
        with override_settings(SOLR_CONNECTIONS={'default': settings.SOLR_CONNECTIONS['test']}):
            output = StringIO("")
            call_command('solr_schema', stdout=output)
            output.seek(0)
            output = output.read()
            assert 'Added ' in output
            assert 'Updated ' not in output

    @pytest.mark.usefixtures("solr")
    def test_update_solr(self):
        with override_settings(SOLR_CONNECTIONS={'default': settings.SOLR_CONNECTIONS['test']}):
            output = StringIO("")
            call_command('solr_schema', stdout=output)
            output.seek(0)
            output = output.read()
            assert 'Updated ' in output
            assert 'Added ' not in output


@pytest.fixture(scope='class')
def ht_pairtree(request):
    '''Override django settings for **HATHI_DATA**and create a temporary
    directory structure mirroring top-level of hathi pairtree data
    (currently has no pairtree content).  Sets list of `hathi_prefixes`
    on the calling class.'''
    # create temporary directories mocking hathi pairtree structure
    tmpdir = tempfile.TemporaryDirectory(prefix='ht_data_')
    prefixes = ['ab', 'cd', 'ef1', 'g23']
    request.cls.hathi_prefixes = prefixes
    with override_settings(HATHI_DATA=tmpdir.name):
        for prefix in prefixes:
            os.mkdir(os.path.join(tmpdir.name, prefix))
        # use yield to ensure tests operate with the overridden settings
        yield prefixes


@pytest.mark.usefixtures("ht_pairtree")
class TestHathiImportCommand(TestCase):

    @patch('ppa.archive.management.commands.hathi_import.pairtree_client')
    def test_initialize_pairtrees(self, mock_pairtree_client):
        cmd = hathi_import.Command()
        cmd.hathi_pairtree = {}  # force pairtree dict to initialize
        cmd.initialize_pairtrees()
        assert cmd.hathi_pairtree
        assert set(cmd.hathi_pairtree.keys()) == set(self.hathi_prefixes)
        for prefix in self.hathi_prefixes:
            mock_pairtree_client.PairtreeStorageClient \
                .assert_any_call(prefix, os.path.join(settings.HATHI_DATA, prefix))

    @patch('ppa.archive.management.commands.hathi_import.pairtree_client')
    def test_get_hathi_ids(self, mock_pairtree_client):
        # pairtree_client.PairtreeStorageClient().list_ids()
        cmd = hathi_import.Command()
        # use the same id values for each prefix
        id_values = ['one', 'two', 'three']
        mock_pairtree_client.PairtreeStorageClient \
            .return_value.list_ids.return_value = id_values
        hathi_ids = cmd.get_hathi_ids()
        # should return a generator so we don't load thousands at once
        assert isinstance(hathi_ids, types.GeneratorType)
        # convert to a list to check ids
        hathi_idlist = list(hathi_ids)
        assert len(hathi_idlist) == len(self.hathi_prefixes) * len(id_values)
        for prefix in self.hathi_prefixes:
            for test_id in id_values:
                assert '%s.%s' % (prefix, test_id) in hathi_idlist

    @patch('ppa.archive.management.commands.hathi_import.pairtree_client')
    def test_get_hathi_ids(self, mock_pairtree_client):
        # pairtree_client.PairtreeStorageClient().list_ids()
        cmd = hathi_import.Command()
        # use the same id values for each prefix
        id_values = ['aa', 'bb', 'cc', 'dd']
        mock_pairtree_client.PairtreeStorageClient \
            .return_value.list_ids.return_value = id_values
        assert cmd.count_hathi_ids() == len(self.hathi_prefixes) * len(id_values)



