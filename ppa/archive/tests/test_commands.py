import json
import os
import queue
import tempfile
import types
from collections import defaultdict
from io import StringIO
from multiprocessing import cpu_count
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
import pytest

from ppa.archive import hathi
from ppa.archive.models import DigitizedWork, Page
from ppa.archive.management.commands import hathi_add, hathi_import, \
    index_pages
from ppa.archive.util import HathiImporter


FIXTURES_PATH = os.path.join(settings.BASE_DIR, 'ppa', 'archive', 'fixtures')


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

    @override_settings(HATHI_DATA='/nonexistent/hathi/data/dir')
    def test_initialize_pairtrees_bad_datadir(self):
        cmd = hathi_import.Command()
        with pytest.raises(CommandError):
            cmd.initialize_pairtrees()

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


# test index pages command and methods


@patch('ppa.archive.management.commands.index_pages.Page')
def test_page_index_data(mock_page):
    work_q = Mock()
    page_q = Mock()
    digwork1 = Mock()
    digwork2 = Mock()
    # return two mock works and then raise queue empty
    work_q.get.side_effect = (digwork1, digwork2, queue.Empty)

    index_pages.page_index_data(work_q, page_q)

    assert work_q.get.call_count == 3
    work_q.get.assert_called_with(timeout=1)
    assert page_q.put.call_count == 2
    page_q.put.assert_any_call(list(mock_page.page_index_data.return_value))
    page_q.put.assert_any_call(list(mock_page.page_index_data.return_value))
    mock_page.page_index_data.assert_any_call(digwork1)
    mock_page.page_index_data.assert_any_call(digwork2)


@patch('ppa.archive.management.commands.index_pages.progressbar')
@patch('ppa.archive.management.commands.index_pages.SolrClient')
def test_process_index_queue(mock_solrclient, mock_progbar):
    work_q = Mock()
    index_q = Mock()
    mockdata1 = ['a', 'b', 'c', 'd']
    mockdata2 = ['y', 'y', 'z']
    # simulate indexer catching up with page index loading
    # - return data, empty, more data, then empty
    index_q.get.side_effect = (mockdata1, queue.Empty, mockdata2, queue.Empty)
    # not empty the first time, empty the second
    work_q.empty.side_effect = (False, True)
    total = 10
    index_pages.process_index_queue(index_q, total, work_q)

    assert index_q.get.call_count == 4
    assert work_q.empty.call_count == 2
    index_q.get.assert_called_with(timeout=5)

    mock_solrclient.return_value.update.index.assert_any_call(mockdata1)
    mock_solrclient.return_value.update.index.assert_any_call(mockdata2)

    mock_progbar.ProgressBar.assert_called_with(redirect_stdout=True,
                                                max_value=total)
    progbar = mock_progbar.ProgressBar.return_value
    progbar.update.assert_any_call(4)
    progbar.update.assert_any_call(7)
    progbar.finish.assert_called_with()


@patch('ppa.archive.management.commands.index_pages.sleep')
@patch('ppa.archive.management.commands.index_pages.progressbar')
@patch('ppa.archive.management.commands.index_pages.Process')
class TestIndexPagesCommand(TestCase):
    fixtures = ['sample_digitized_works']

    @pytest.mark.usefixtures("mock_solr_queryset")
    def test_index_pages(self, mock_process, mock_progbar, mock_sleep):
        # generate solrqueryset mock and patch it in
        mock_solrqs = self.mock_solr_queryset()
        with patch('ppa.archive.management.commands.index_pages.SolrQuerySet',
                   new=mock_solrqs):
            mock_solrqs.return_value.get_facets.return_value \
                .facet_fields.item_type = {'pages': 153}

            # test calling from command line
            stdout = StringIO()
            call_command('index_pages', stdout=stdout)

            # Process should be called at least twice
            assert mock_process.call_count >= 2
            # could inspect to confirm called correctly, but probably
            # requires

            output = stdout.getvalue()
            assert 'Indexing with %d processes' % cpu_count() in output
            assert 'Items in Solr by item type:' in output

    def test_index_pages_quiet(self, mock_process, mock_progbar, mock_sleep):
        # test calling from command line
        stdout = StringIO()
        call_command('index_pages', stdout=stdout, verbosity=0)
        output = stdout.getvalue()
        assert 'Indexing with' not in output
        assert 'Items in Solr' not in output
