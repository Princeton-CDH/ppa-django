from collections import defaultdict
from datetime import date, timedelta
from io import StringIO
import json
import os
import tempfile
import types
from unittest.mock import patch, Mock
from zipfile import ZipFile

from django.conf import settings
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from pairtree import pairtree_client, pairtree_path
import pytest
from SolrClient import SolrClient

from ppa.archive.hathi import HathiBibliographicAPI, HathiItemNotFound, \
    HathiBibliographicRecord
from ppa.archive.models import DigitizedWork
from ppa.archive.management.commands import hathi_import
from ppa.archive.solr import SolrSchema, CoreAdmin


FIXTURES_PATH = os.path.join(settings.BASE_DIR, 'ppa', 'archive', 'fixtures')


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
            # don't delete default/built-in fields!
            if field == 'id' or field.startswith('_'):
                continue
            solr_schema.solr.schema.delete_field(solr_schema.solr_collection, field)
        CoreAdmin().reload()

        # yield settings so tests run with overridden solr connection
        yield settings



@pytest.fixture
def solr():
    # pytest solr fixture; updates solr schema
    with override_settings(SOLR_CONNECTIONS={'default': settings.SOLR_CONNECTIONS['test']}):
        # reload core before and after to ensure field list is accurate
        CoreAdmin().reload()
        SolrSchema().update_solr_schema()
        CoreAdmin().reload()

        # yield settings so tests run with overridden solr connection
        yield settings


class TestSolrSchemaCommand(TestCase):

    def test_connection_error(self):
        # simulate no solr running
        with override_settings(SOLR_CONNECTIONS={'default':
                              {'COLLECTION': 'bogus',
                               'URL': 'http://localhost:191918984/solr/'}}):
            with pytest.raises(CommandError):
                call_command('solr_schema')

    # @pytest.mark.skip   # skip for now - causing an error on travis-ci
    @pytest.mark.usefixtures("empty_solr")
    def test_empty_solr(self):
        stdout = StringIO()
        call_command('solr_schema', stdout=stdout)
        output = stdout.getvalue()
        assert 'Added ' in output
        assert 'Updated ' not in output

    @pytest.mark.usefixtures("solr")
    def test_update_solr(self):
        stdout = StringIO()
        call_command('solr_schema', stdout=stdout)
        output = stdout.getvalue()
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
        cmd.hathi_pairtree = {}  # force pairtree dict to initialize
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
    def test_count_hathi_ids(self, mock_pairtree_client):
        # pairtree_client.PairtreeStorageClient().list_ids()
        cmd = hathi_import.Command()
        # use the same id values for each prefix
        id_values = ['aa', 'bb', 'cc', 'dd']
        mock_pairtree_client.PairtreeStorageClient \
            .return_value.list_ids.return_value = id_values
        assert cmd.count_hathi_ids() == len(self.hathi_prefixes) * len(id_values)

    def test_import_digitizedwork(self):
        cmd = hathi_import.Command(stdout=StringIO())
        cmd.bib_api = Mock(spec=HathiBibliographicAPI)
        cmd.stats = defaultdict(int)

        # simulate record not found
        cmd.bib_api.record.side_effect = HathiItemNotFound
        assert cmd.import_digitizedwork('ht.12345') is None
        assert cmd.stats['error'] == 1
        assert DigitizedWork.objects.all().count() == 0
        # cmd.stdout.seek(0)
        assert 'Bibliographic data not found' in cmd.stdout.getvalue() #read()

        # create new record
        cmd.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        bibdata_full = os.path.join(FIXTURES_PATH, 'bibdata_full_njp.32101013082597.json')
        cmd.bib_api.record.side_effect = None
        with open(bibdata_full) as bibdata:
            hathirecord = HathiBibliographicRecord(json.load(bibdata))
            cmd.bib_api.record.return_value = hathirecord
        # reset stats
        cmd.stats = defaultdict(int)
        htid = 'njp.32101013082597'
        digwork = cmd.import_digitizedwork(htid)
        assert isinstance(digwork, DigitizedWork)
        # get from db to confirm record details were saved
        digwork = DigitizedWork.objects.get(source_id=htid)
        # metadata should be set via bibdata
        assert digwork.title
        # log entry should exist for record creation
        log_entry = LogEntry.objects.get(object_id=digwork.id)
        assert log_entry.user == cmd.script_user
        assert log_entry.content_type == ContentType.objects.get_for_model(digwork)
        assert log_entry.change_message == 'Created via hathi_import script'
        assert log_entry.action_flag == ADDITION
        assert cmd.stats['created'] == 1
        assert not cmd.stats['error']
        assert not cmd.stats['updated']

        # import existing with no update requested/needed
        # reset stats
        cmd.stats = defaultdict(int)
        cmd.stdout = StringIO()
        cmd.options = {'update': False}
        cmd.verbosity = 2
        assert cmd.import_digitizedwork(htid) is None
        assert cmd.stats['skipped'] == 1
        assert 'no update needed' in cmd.stdout.getvalue()

        # simulate hathi record updated since import
        cmd.stats = defaultdict(int)
        cmd.stdout = StringIO()
        cmd.options = {'update': False}  # no force update
        cmd.verbosity = 2
        with patch.object(hathirecord, 'copy_last_updated') as mock_lastupdated:
            # using tomorrow to ensure date is after local record modification
            tomorrow = date.today() + timedelta(days=1)
            mock_lastupdated.return_value = tomorrow
            digwork = cmd.import_digitizedwork(htid)
            assert digwork
            assert cmd.stats['updated'] == 1
            assert cmd.stats['skipped'] == 0
            assert 'record last updated %s, updated needed' % tomorrow in \
                cmd.stdout.getvalue()

        # log entry should exist for record update; get newest
        log_entry = LogEntry.objects.filter(object_id=digwork.id) \
            .order_by('-action_time').first()
        assert log_entry.user == cmd.script_user
        assert log_entry.content_type == ContentType.objects.get_for_model(digwork)
        assert 'Updated via hathi_import script' in log_entry.change_message
        assert 'source record last updated %s' % tomorrow in log_entry.change_message
        assert log_entry.action_flag == CHANGE

        # update requested by user
        cmd.stats = defaultdict(int)
        cmd.stdout = StringIO()
        cmd.options = {'update': True}  # force update
        cmd.verbosity = 2
        assert cmd.import_digitizedwork(htid)
        assert cmd.stats['updated'] == 1
        assert cmd.stats['skipped'] == 0

        # check newest log entry for this object
        log_entry = LogEntry.objects.filter(object_id=digwork.id) \
            .order_by('-action_time').first()
        assert log_entry.user == cmd.script_user
        assert log_entry.content_type == ContentType.objects.get_for_model(digwork)
        assert 'Updated via hathi_import script' in log_entry.change_message
        assert ' (forced update)' in log_entry.change_message
        assert log_entry.action_flag == CHANGE

    @patch('ppa.archive.management.commands.hathi_import.ZipFile', spec=ZipFile)
    def test_index_pages(self, mockzipfile):
        cmd = hathi_import.Command(stdout=StringIO())
        cmd.stats = defaultdict(int)
        prefix, pt_id = ('ab', '12345:6')
        mock_pairtree_client = Mock(spec=pairtree_client.PairtreeStorageClient)
        cmd.hathi_pairtree = {prefix: mock_pairtree_client}
        cmd.solr = Mock(spec=SolrClient)
        cmd.solr_collection = 'testidx'
        digwork = DigitizedWork(source_id='.'.join([prefix, pt_id]))

        pt_obj = mock_pairtree_client.get_object.return_value
        pt_obj.list_parts.return_value = ['12345.mets.xml', '12345.zip']
        pt_obj.id_to_dirpath.return_value = 'ab/path/12345+6'
        # parts = ptobj.list_parts(content_dir)
        # __enter__ required because zipfile used as context block
        mockzip_obj = mockzipfile.return_value.__enter__.return_value
        page_files = ['0001.txt', '00002.txt']
        mockzip_obj.namelist.return_value = page_files
        # simulate reading zip file contents
        mockzip_obj.open.return_value.__enter__.return_value \
            .read.return_value.decode.return_value = 'page content'

        # actually index the content
        cmd.index_pages(digwork)

        # inspect pairtree logic
        mock_pairtree_client.get_object.assert_any_call(pt_id, create_if_doesnt_exist=False)
        # list parts called on encoded version of pairtree id
        content_dir = pairtree_path.id_encode(pt_id)
        pt_obj.list_parts.assert_any_call(content_dir)
        pt_obj.id_to_dirpath.assert_any_call()

        # inspect zipfile logic
        mockzip_obj.namelist.assert_called_with()
        for filename in mockzip_obj.namelist():
            mockzip_obj.open.assert_any_call(filename)

        zipfile_path = os.path.join(pt_obj.id_to_dirpath(), content_dir, '12345.zip')
        mockzipfile.assert_called_with(zipfile_path)

        # stats and digitized work page counts updated
        assert cmd.stats['pages'] == 2
        digwork = DigitizedWork.objects.get(source_id=digwork.source_id)
        assert digwork.page_count == 2

        # inspect solr index data
        solr_idx_args, solr_idx_kwargs = cmd.solr.index.call_args
        assert solr_idx_args[0] == cmd.solr_collection
        solr_docs = solr_idx_args[1]
        # first solr doc is for the work
        assert solr_docs[0] == digwork.index_data()
        # subsequent solr docs for the pages
        page_index_data = solr_docs[1]
        assert page_index_data['srcid'] == digwork.source_id
        assert page_index_data['item_type'] == 'page'
        # page id based on source id + filename
        page_label = page_files[0].replace('.txt', '')
        assert page_index_data['id'] == '.'.join([digwork.source_id, page_label])
        assert page_index_data['order'] == page_label
        assert page_index_data['content'] == 'page content'

        page_index_data = solr_docs[2]
        page_label = page_files[1].replace('.txt', '')
        assert page_index_data['srcid'] == digwork.source_id
        assert page_index_data['id'] == '.'.join([digwork.source_id, page_label])
        assert page_index_data['order'] == page_label

        # exact value not important, just that it's present
        assert 'commitWithin' in solr_idx_kwargs['params']

    @patch('ppa.archive.management.commands.hathi_import.HathiBibliographicAPI')
    @patch('ppa.archive.management.commands.hathi_import.progressbar')
    @patch('ppa.archive.management.commands.hathi_import.get_solr_connection')
    def test_call_command(self, mock_get_solr, mockprogbar, mockhathi_bibapi):

        # patch methods with actual logic to check handle method behavior
        with patch.object(hathi_import.Command, 'get_hathi_ids') as mock_get_htids, \
          patch.object(hathi_import.Command, 'initialize_pairtrees') as mock_init_ptree, \
          patch.object(hathi_import.Command, 'import_digitizedwork') as mock_import_digwork, \
          patch.object(hathi_import.Command, 'index_pages') as mock_index_pages:

            mock_htids = ['ab.1234', 'cd.5678']
            mock_get_htids.return_value = mock_htids
            digwork = DigitizedWork(source_id='test.123')
            mock_import_digwork.return_value = digwork
            mock_get_solr.return_value = (Mock, 'testcoll')

            # default behavior = read ids from pairtree
            stdout = StringIO()
            call_command('hathi_import', stdout=stdout)

            mock_init_ptree.assert_any_call()
            for htid in mock_htids:
                mock_import_digwork.assert_any_call(htid)
            mock_index_pages.assert_called_with(digwork)

            output = stdout.getvalue()
            assert 'Processed 2 items for import.' in output

            # request specific ids
            call_command('hathi_import', 'htid1', 'htid2', stdout=stdout)
            mock_import_digwork.assert_any_call('htid1')
            mock_import_digwork.assert_any_call('htid2')

            # request progress bar
            call_command('hathi_import', progress=1, verbosity=0, stdout=stdout)
            mockprogbar.ProgressBar.assert_called_with(redirect_stdout=True,
                    max_value=len(mock_htids))
