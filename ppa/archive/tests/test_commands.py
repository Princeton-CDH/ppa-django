from collections import defaultdict
from io import StringIO
import json
import os
import tempfile
import types
from unittest.mock import patch, Mock

from django.conf import settings
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
import pytest

from ppa.archive import hathi
from ppa.archive.models import DigitizedWork
from ppa.archive.management.commands import hathi_import, index, hathi_add
from ppa.archive.solr import get_solr_connection
from ppa.archive.util import HathiImporter


FIXTURES_PATH = os.path.join(settings.BASE_DIR, 'ppa', 'archive', 'fixtures')

class TestSolrSchemaCommand(TestCase):

    def test_connection_error(self):
        # simulate no solr running
        with override_settings(SOLR_CONNECTIONS={'default':
                              {'COLLECTION': 'bogus',
                               'URL': 'http://localhost:9876/solr/'}}):
            with pytest.raises(CommandError):
                call_command('solr_schema')

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

        # create field to be removed
        solr, coll = get_solr_connection()
        solr.schema.create_field(
            coll, {'name': 'bogus', 'type': 'string', 'required': False})
        call_command('solr_schema', stdout=stdout)
        output = stdout.getvalue()
        assert 'Removed 1 field' in output


@pytest.fixture(scope='class')
def ht_pairtree(request):
    '''Override django settings for **HATHI_DATA**and create a temporary
    directory structure mirroring top-level of hathi pairtree data
    (currently has no pairtree content).  Sets list of `hathi_prefixes`
    on the calling class.'''
    # create temporary directories mocking hathi pairtree structure
    with tempfile.TemporaryDirectory(prefix='ht_data_') as tmpdir_name:
        prefixes = ['ab', 'cd', 'ef1', 'g23']
        request.cls.hathi_prefixes = prefixes
        with override_settings(HATHI_DATA=tmpdir_name):
            for prefix in prefixes:
                os.mkdir(os.path.join(tmpdir_name, prefix))
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

    @pytest.mark.usefixtures('solr')
    def test_import_digitizedwork(self):
        cmd = hathi_import.Command(stdout=StringIO())
        cmd.bib_api = Mock(spec=hathi.HathiBibliographicAPI)
        cmd.stats = defaultdict(int)

        # simulate record not found
        cmd.options['update'] = False
        cmd.digwork_content_type = ContentType.objects.get_for_model(DigitizedWork)
        cmd.bib_api.record.side_effect = hathi.HathiItemNotFound
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
            hathirecord = hathi.HathiBibliographicRecord(json.load(bibdata))
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
        assert cmd.import_digitizedwork(htid) == digwork
        assert cmd.stats['skipped'] == 1
        assert 'no update needed' in cmd.stdout.getvalue()

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

    @patch('ppa.archive.management.commands.hathi_import.HathiBibliographicAPI')
    @patch('ppa.archive.management.commands.hathi_import.progressbar')
    def test_call_command(self, mockprogbar, mockhathi_bibapi):

        digwork = DigitizedWork(source_id='test.123')

        # patch methods with actual logic to check handle method behavior
        with patch.object(hathi_import.Command, 'get_hathi_ids') as mock_get_htids, \
          patch.object(hathi_import.Command, 'initialize_pairtrees') as mock_init_ptree, \
          patch.object(hathi_import.Command, 'import_digitizedwork') as mock_import_digwork, \
          patch.object(digwork, 'count_pages') as mock_count_pages:

            mock_htids = ['ab.1234', 'cd.5678']
            mock_get_htids.return_value = mock_htids
            mock_import_digwork.return_value = digwork
            mock_count_pages.return_value = 10

            # default behavior = read ids from pairtree
            stdout = StringIO()
            call_command('hathi_import', stdout=stdout)

            mock_init_ptree.assert_any_call()
            for htid in mock_htids:
                mock_import_digwork.assert_any_call(htid)
            mock_count_pages.assert_any_call()

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


class TestIndexCommand(TestCase):
    fixtures = ['sample_digitized_works']

    @patch('ppa.archive.management.commands.index.Indexable')
    def test_index(self, mockindexable):
        # index data into solr and catch  an error
        cmd = index.Command()
        cmd.solr = Mock()
        cmd.solr_collection = 'test'

        test_index_data = range(5)
        cmd.index(test_index_data)
        mockindexable.index_items.assert_called_with(test_index_data, progbar=None)

        # solr connection exception should raise a command error
        with pytest.raises(CommandError):
            mockindexable.index_items.side_effect = Exception
            cmd.index(test_index_data)

    def test_clear(self):
        # index data into solr and catch  an error
        cmd = index.Command()
        cmd.solr = Mock()
        cmd.solr_collection = 'test'

        cmd.clear('all')
        cmd.solr.delete_doc_by_query.assert_called_with(cmd.solr_collection, '*:*')

        cmd.solr.reset_mock()
        cmd.clear('works')
        cmd.solr.delete_doc_by_query.assert_called_with(cmd.solr_collection, 'item_type:work')

        cmd.solr.reset_mock()
        cmd.clear('pages')
        cmd.solr.delete_doc_by_query.assert_called_with(cmd.solr_collection, 'item_type:page')

        cmd.solr.reset_mock()
        cmd.clear('foo')
        cmd.solr.delete_doc_by_query.assert_not_called()

        cmd.stdout = StringIO()
        cmd.verbosity = 3
        cmd.clear('works')
        assert cmd.stdout.getvalue() == 'Clearing works from the index'

    @patch('ppa.archive.management.commands.index.get_solr_connection')
    @patch('ppa.archive.management.commands.index.progressbar')
    @patch.object(index.Command, 'index')
    def test_call_command(self, mock_cmd_index_method, mockprogbar, mock_get_solr):
        mocksolr = Mock()
        test_coll = 'test'
        mock_get_solr.return_value = (mocksolr, test_coll)
        digworks = DigitizedWork.objects.all()

        stdout = StringIO()
        call_command('index', index='works', stdout=stdout)

        # index all works
        # (can't use assert_called_with because querysets doesn't evaluate equal)
        # mock_cmd_index_method.assert_called_with(digworks)
        args = mock_cmd_index_method.call_args[0]
        # first arg is queryset; compare them as lists
        assert list(digworks) == list(args[0])

        # not enough data to run progress bar
        mockprogbar.ProgressBar.assert_not_called()
        # commit called after works are indexed
        mocksolr.commit.assert_called_with(test_coll, openSearcher=True)
        # only called once (no pages)
        assert mock_cmd_index_method.call_count == 1

        with patch.object(DigitizedWork, 'page_index_data') as mock_page_index_data:
            mock_cmd_index_method.reset_mock()
            total_works = digworks.count()
            total_pages = sum(work.page_count for work in digworks)

            # simple number generator to test indexing in chunks
            def test_generator():
                for i in range(155):
                    yield i

            mock_page_index_data.side_effect = test_generator

            call_command('index', index='pages', stdout=stdout)

            # progressbar should be called
            mockprogbar.ProgressBar.assert_called_with(
                redirect_stdout=True, max_value=total_pages)
            # page index data called once for each work
            assert mock_page_index_data.call_count == total_works
            # progress bar updated called once for each work
            mockprogbar.ProgressBar.return_value.update.call_count = total_works
            # mock index called once for each work (chunking handled in Indexable)
            assert mock_cmd_index_method.call_count == total_works

            # request no progress bar
            mockprogbar.reset_mock()
            call_command('index', index='pages', no_progress=True, stdout=stdout)
            mockprogbar.ProgressBar.assert_not_called()

            # index both works and pages (default behavior)
            mock_cmd_index_method.reset_mock()
            mock_page_index_data.reset_mock()
            call_command('index', stdout=stdout)
            # progressbar should be called, total = works + pages
            mockprogbar.ProgressBar.assert_called_with(
                redirect_stdout=True, max_value=total_works + total_pages)
            # called once for the works (all indexed in one batch) and
            # once for each set of pages in a work
            assert mock_cmd_index_method.call_count == total_works + 1
            # page index data called
            assert mock_page_index_data.call_count == total_works

            # index a single work by id
            work = digworks.first()
            mock_cmd_index_method.reset_mock()
            mock_page_index_data.reset_mock()
            call_command('index', work.source_id, stdout=stdout)
            mockprogbar.ProgressBar.assert_called_with(
                redirect_stdout=True, max_value=1 + work.page_count)
            # called once for the work and once for the pages
            assert mock_cmd_index_method.call_count == 2
            # page index data called once only
            assert mock_page_index_data.call_count == 1

            # index nothing
            mock_cmd_index_method.reset_mock()
            mock_page_index_data.reset_mock()
            call_command('index', index='none', stdout=stdout)
            assert not mock_cmd_index_method.call_count
            assert not mock_page_index_data.call_count

    @patch('ppa.archive.management.commands.index.get_solr_connection')
    @patch('ppa.archive.management.commands.index.progressbar')
    @patch.object(index.Command, 'index')
    def test_skip_suppressed(self, mock_cmd_index_method, mockprogbar, mock_get_solr):
        mocksolr = Mock()
        test_coll = 'test'
        mock_get_solr.return_value = (mocksolr, test_coll)

        # mark one as suppressed
        work = DigitizedWork.objects.first()
        work.status = DigitizedWork.SUPPRESSED

        # skip hathi data deletion when suppressed
        with patch.object(work, 'hathi'):
            work.save()

        # digworks = DigitizedWork.objects.filter(status=DigitizedWork.PUBLIC)

        stdout = StringIO()
        call_command('index', index='works', stdout=stdout)

        # index all works
        # (can't use assert_called_with because querysets doesn't evaluate equal)
        # mock_cmd_index_method.assert_called_with(digworks)
        args = mock_cmd_index_method.call_args[0]
        # first arg is queryset; compare them as lists
        # assert list(digworks) == list(args[0])
        assert work not in list(args[0])


class TestHathiAddCommand(TestCase):
    fixtures = ['sample_digitized_works']

    def test_ids_to_process(self):
        cmd = hathi_add.Command()
        cmd.stats = defaultdict(int)
        cmd.stdout = StringIO()

        # ids via command line
        htids = ['1', '2', '3']
        cmd.options['htids'] = htids
        cmd.options['file'] = None
        assert cmd.ids_to_process() == htids

        # list of ids in a file
        idfile = tempfile.NamedTemporaryFile(prefix='ht-add-ids', suffix='txt')
        new_file_ids = ['a', 'b', 'c', 'd', 'efg', 'xyz', ' ']
        idfile.write('\n'.join(new_file_ids).encode())
        idfile.flush()  # write out to disk
        cmd.options['htids'] = []
        cmd.options['file'] = idfile.name
        # should include all but the empty line at the end
        assert cmd.ids_to_process() == new_file_ids[:-1]

    @patch('ppa.archive.management.commands.hathi_add.HathiImporter')
    def test_call_command(self, mock_hathi_importer):
        stdout = StringIO()
        mock_htimporter = mock_hathi_importer.return_value
        # copy constants to the mock
        mock_hathi_importer.SUCCESS = HathiImporter.SUCCESS
        mock_hathi_importer.SKIPPED = HathiImporter.SKIPPED

        digwork_ids = DigitizedWork.objects.values_list('source_id', flat=True)
        # call on existing ids - all should be skipped

        # simulate all ids existing
        mock_htimporter.existing_ids = dict((dw_id, '') for dw_id in digwork_ids)

        call_command('hathi_add', *digwork_ids, stdout=stdout, verbosity=3)

        # should initialize importer with htids
        mock_hathi_importer.assert_called_with(list(digwork_ids))
        # should filter out existing ids
        mock_htimporter.filter_existing_ids.assert_called_with()
        # should call add items
        mock_htimporter.add_items.assert_called_with(log_msg_src='via hathi_add script')
        # should call index
        mock_htimporter.index.assert_called_with()
        # should report skipped ids
        output = stdout.getvalue()
        assert 'Skipping ids already present:' in output
        assert 'skipped %d' % len(digwork_ids) in output

        # call with new id - simulate error
        stderr = StringIO()
        stdout = StringIO()
        test_htid = 'xyz:9876'
        mock_htimporter.existing_ids = {}
        mock_htimporter.results = {test_htid: hathi.HathiItemNotFound()}
        # simulate what would be generated by output results method
        mock_htimporter.output_results.return_value = {
            test_htid: HathiImporter.status_message[hathi.HathiItemNotFound]
        }
        call_command('hathi_add', test_htid, stdout=stdout, stderr=stderr,
                     verbosity=3)
        err_output = stderr.getvalue()
        output = stdout.getvalue()
        # human-readable error results output
        expected_err_msg = '%s - %s' % \
            (test_htid, HathiImporter.status_message[hathi.HathiItemNotFound])
        assert expected_err_msg in err_output
        assert '1 error' in output

        # simulate success
        stdout = StringIO()
        test_htid = 'stu:6381'
        mock_htimporter.results = {test_htid: HathiImporter.SUCCESS}
        mock_htimporter.imported_works = [Mock(page_count=550)]
        call_command('hathi_add', test_htid, stdout=stdout, verbosity=3)
        output = stdout.getvalue()
        assert 'Processed 1 item' in output
        assert 'Added 1' in output
        assert 'imported 550 pages' in output
        # success by pid
        assert '%s - successfully added' % test_htid in output

        # success not reported when less verbose
        stdout = StringIO()
        call_command('hathi_add', test_htid, stdout=stdout, verbosity=0)
        output = stdout.getvalue()
        # success by pid
        assert '%s - successfully added' % test_htid not in output

