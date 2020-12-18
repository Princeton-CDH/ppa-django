from collections import OrderedDict
from unittest.mock import patch, Mock
from json.decoder import JSONDecodeError

from django.conf import settings
from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
import pytest

from ppa.archive import hathi
from ppa.archive.models import DigitizedWork
from ppa.archive.util import HathiImporter


class TestHathiImporter(TestCase):
    fixtures = ['sample_digitized_works']

    def test_filter_existing_ids(self):

        digwork_ids = DigitizedWork.objects.values_list('source_id', flat=True)

        # all existing - all should be flagged as existing
        htimporter = HathiImporter(digwork_ids)
        htimporter.filter_existing_ids()
        # no ht ids left, all marked existing
        assert not htimporter.htids
        assert len(htimporter.existing_ids) == len(digwork_ids)
        # existing_ids should be dict with source id -> pk
        digwork = DigitizedWork.objects.first()
        assert htimporter.existing_ids[digwork.source_id] == digwork.pk

        # mix of new and existing ids
        new_ids = ['one.1', 'two.2', 'three.3']
        htimporter = HathiImporter(new_ids + list(digwork_ids))
        htimporter.filter_existing_ids()
        assert len(htimporter.existing_ids) == len(digwork_ids)
        assert set(htimporter.htids) == set(new_ids)

    def test_filter_invalid_ids(self):
        htimporter = HathiImporter(['mdp.1234', 'foobar'])
        htimporter.filter_invalid_ids()
        # first should stay, second should be removed
        assert 'mdp.1234' in htimporter.htids
        assert 'foobar' not in htimporter.htids

    @override_settings(HATHI_DATA='/my/test/ppa/ht_data')
    @patch('ppa.archive.util.os.path.isdir')
    @patch('ppa.archive.util.glob.glob')
    @patch('ppa.archive.models.DigitizedWork.add_from_hathi')
    def test_add_items_notfound(self, mock_add_from_hathi, mock_glob,
                                mock_isdir):
        test_htid = 'a.123'
        htimporter = HathiImporter([test_htid])
        # unlikely scenario, but simulate rsync success with bib api failure
        mock_isdir.return_value = True  # directory exists
        mock_glob.return_value = ['foo.zip']   # zipfile exists

        with patch.object(htimporter, 'rsync_data') as mock_rsync_data:
            # simulate record not found
            mock_add_from_hathi.side_effect = hathi.HathiItemNotFound
            htimporter.add_items()
            mock_rsync_data.assert_called_with()
            mock_add_from_hathi.assert_called_with(
                test_htid, htimporter.bib_api,
                log_msg_src=None, user=None)
            assert not htimporter.imported_works
            # actual error stored in results
            assert isinstance(htimporter.results[test_htid],
                              hathi.HathiItemNotFound)
            # no partial record hanging around
            assert not DigitizedWork.objects.filter(source_id=test_htid)

    @override_settings(HATHI_DATA='/my/test/ppa/ht_data')
    @patch('ppa.archive.util.os.path.isdir')
    @patch('ppa.archive.util.glob.glob')
    @patch('ppa.archive.models.DigitizedWork.add_from_hathi')
    def test_add_items_rsync_failure(self, mock_add_from_hathi, mock_glob,
                                     mock_isdir):
        test_htid = 'a.123'
        htimporter = HathiImporter([test_htid])

        with patch.object(htimporter, 'rsync_data') as mock_rsync_data:
            # simulate directory not created
            mock_isdir.return_value = False

            # do nothing: expected directory not created by rsync
            log_msg_src = 'from unit test'
            htimporter.add_items(log_msg_src)
            mock_rsync_data.assert_called_with()

            assert mock_add_from_hathi.call_count == 0

            # error code stored in results
            assert htimporter.results[test_htid] == htimporter.RSYNC_ERROR
            # no partial record hanging around
            assert not DigitizedWork.objects.filter(source_id=test_htid)

            # simulate directory created but no zip file
            # — should still get an rsync error
            mock_isdir.return_value = True
            mock_glob.return_value = []
            log_msg_src = 'from unit test'
            htimporter.add_items(log_msg_src)
            mock_rsync_data.assert_called_with()

            assert mock_add_from_hathi.call_count == 0

            # error code stored in results
            assert htimporter.results[test_htid] == htimporter.RSYNC_ERROR

    @patch('ppa.archive.util.os.path.isdir')
    @patch('ppa.archive.util.glob.glob')
    @patch('ppa.archive.models.DigitizedWork.page_count')
    @patch('ppa.archive.models.DigitizedWork.add_from_hathi')
    @override_settings(HATHI_DATA='/my/test/ppa/ht_data')
    def test_add_items_success(self, mock_page_count, mock_add_from_hathi,
                               mock_glob, mock_isdir):
        test_htid = 'a.123'
        htimporter = HathiImporter([test_htid])
        # simulate rsync success
        mock_isdir.return_value = True  # directory exists
        mock_glob.return_value = ['foo.zip']   # zipfile exists

        # simulate success
        def fake_add_from_hathi(htid, *args, **kwargs):
            '''fake add_from_hathi method to create
            a new digwork and corresponding log entry'''
            digwork = DigitizedWork.objects.create(source_id=htid,
                                                   page_count=1337)
            # create log entry for record creation
            LogEntry.objects.log_action(
                user_id=User.objects.get(username=settings.SCRIPT_USERNAME).pk,
                content_type_id=ContentType.objects.get_for_model(digwork).pk,
                object_id=digwork.pk,
                object_repr=str(digwork),
                change_message='Created %s' % log_msg_src,
                action_flag=ADDITION)

            return digwork
        mock_add_from_hathi.side_effect = fake_add_from_hathi

        with patch.object(htimporter, 'rsync_data'):
            log_msg_src = 'from unit test'
            htimporter.add_items(log_msg_src)
            assert len(htimporter.imported_works) == 1
            assert htimporter.results[test_htid] == HathiImporter.SUCCESS

    @patch('ppa.archive.util.DigitizedWork')
    @patch('ppa.archive.util.Page')
    def test_index(self, mock_page, mock_digitizedwork):
        test_htid = 'a:123'
        htimporter = HathiImporter([test_htid])
        # no imported works, index should do nothing
        htimporter.index()
        mock_digitizedwork.index_items.assert_not_called()

        # simulate imported work to index
        mock_digwork = Mock()
        htimporter.imported_works = [mock_digwork]
        htimporter.index()
        mock_digitizedwork.index_items.assert_any_call(htimporter.imported_works)
        mock_page.page_index_data.assert_called_with(mock_digwork)
        mock_digitizedwork.index_items.assert_any_call(mock_page.page_index_data())

    def test_get_status_message(self):
        htimporter = HathiImporter(['a.123'])
        # simple status codes
        assert htimporter.get_status_message(HathiImporter.SUCCESS) == \
            HathiImporter.status_message[HathiImporter.SUCCESS]
        assert htimporter.get_status_message(HathiImporter.SKIPPED) == \
            HathiImporter.status_message[HathiImporter.SKIPPED]
        # error classses
        assert htimporter.get_status_message(hathi.HathiItemNotFound()) == \
            HathiImporter.status_message[hathi.HathiItemNotFound]
        assert htimporter.get_status_message(hathi.HathiItemForbidden()) == \
            HathiImporter.status_message[hathi.HathiItemForbidden]
        assert htimporter.get_status_message(Mock(spec=JSONDecodeError)) == \
            HathiImporter.status_message[JSONDecodeError]

        # error for anything else
        with pytest.raises(KeyError):
            htimporter.get_status_message('foo')

    def test_output_results(self):
        htimporter = HathiImporter(['a.123'])
        # set sample results to test - one of each
        success_id = 'added:1'
        notfound_id = 'err:404'

        # htimporter.results = {
        htimporter.results = OrderedDict([
            (success_id, HathiImporter.SUCCESS),
            (notfound_id, hathi.HathiItemNotFound()),
        ])
        output_results = htimporter.output_results()
        # length of output results should match results
        assert len(output_results) == len(htimporter.results)
        # message should be set for each based on value or type of status
        assert output_results[success_id] == \
            HathiImporter.status_message[HathiImporter.SUCCESS]
        assert output_results[notfound_id] == \
            HathiImporter.status_message[hathi.HathiItemNotFound]

    def test_pairtree_paths(self):
        htimporter = HathiImporter(['hvd.1234', 'nyp.334455'])
        # returns a generator; convert to list for inspection
        pairtree_paths = htimporter.pairtree_paths
        assert pairtree_paths['hvd.1234'] == 'hvd/pairtree_root/12/34'
        assert pairtree_paths['nyp.334455'] == 'nyp/pairtree_root/33/44/55'
        # includes prefix and version files
        assert pairtree_paths['hvd'] == 'hvd/pairtree_prefix'
        assert pairtree_paths['hvd_version'] == 'hvd/pairtree_version*'
        assert pairtree_paths['nyp'] == 'nyp/pairtree_prefix'
        assert pairtree_paths['nyp_version'] == 'nyp/pairtree_version*'

    @override_settings(HATHI_DATA='/my/test/ppa/ht_data',
                       HATHITRUST_RSYNC_SERVER='data.ht.org',
                       HATHITRUST_RSYNC_PATH=':ht_text_pd')
    @patch('ppa.archive.util.subprocess')
    def test_rsync_data(self, mocksubprocess):
        htimporter = HathiImporter(['hvd.1234', 'nyp.334455'])
        htimporter.rsync_data()
        assert mocksubprocess.run.call_count == 1
        args, kwargs = mocksubprocess.run.call_args
        cmd_args = kwargs['args']
        # quick check that command is split properly
        assert cmd_args[0] == 'rsync'
        assert cmd_args[1] == '-rLt'
        # last arg is local path for data destination
        assert cmd_args[-1] == '/my/test/ppa/ht_data'
        # second to last arg is server:src; use defaults from settings
        assert cmd_args[-2] == 'data.ht.org::ht_text_pd'
        # third from last arg is file list
        assert cmd_args[-3].startswith('--files-from=')
        assert 'ppa_hathi_pathlist' in cmd_args[-3]
