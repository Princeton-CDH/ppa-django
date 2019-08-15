from datetime import date
import os.path
from unittest.mock import patch, Mock
import json
import tempfile

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from eulxml.xmlmap import load_xmlobject_from_file
from pairtree import pairtree_client, pairtree_path, storage_exceptions
import pymarc
import pytest
import requests
import requests_oauthlib

from ppa import __version__
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

        print(mocksession.get.call_args_list)
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

@patch('ppa.archive.hathi.requests')
class TestHathiBaseAPI(TestCase):

    def test_init(self, mockrequests):
        # test session initialization

        # no technical contact
        with override_settings(TECHNICAL_CONTACT=None):
            base_user_agent = 'requests/v123'
            mockrequests.Session.return_value.headers = {'User-Agent': base_user_agent}
            base_api = hathi.HathiBaseAPI()
            mockrequests.Session.assert_any_call()
            assert base_api.session == mockrequests.Session.return_value
            assert 'ppa-django' in base_api.session.headers['User-Agent']
            assert __version__ in base_api.session.headers['User-Agent']
            assert '(%s)' % base_user_agent in base_api.session.headers['User-Agent']
            assert 'From' not in base_api.session.headers

        # technical contact configured
        tech_contact = 'webmaster@example.com'
        with override_settings(TECHNICAL_CONTACT=tech_contact):
            base_api = hathi.HathiBaseAPI()
            assert base_api.session.headers['From'] == tech_contact

    def test_make_request(self, mockrequests):
        base_api = hathi.HathiBaseAPI()
        base_api.api_root = 'http://example.com/api'

        mockrequests.codes = requests.codes

        # mock successful request
        base_api.session.get.return_value.status_code = requests.codes.ok
        resp = base_api._make_request('foo')
        base_api.session.get.assert_called_with('%s/foo' % base_api.api_root)
        assert resp == base_api.session.get.return_value

        # 404 not found response should raise item not found
        base_api.session.get.return_value.status_code = requests.codes.not_found
        with pytest.raises(hathi.HathiItemNotFound):
            base_api._make_request('foo')

        # 403 forbidden response should raise item forbidden
        base_api.session.get.return_value.status_code = requests.codes.forbidden
        with pytest.raises(hathi.HathiItemForbidden):
            base_api._make_request('foo')


class TestHathiDataAPI(TestCase):

    test_hathi_key = 'mykey'
    test_hathi_secret = 'mysecret'
    test_hathi_opts = {
        'HATHITRUST_OAUTH_KEY': test_hathi_key,
        'HATHITRUST_OAUTH_SECRET': test_hathi_secret
    }

    def test_init(self):
        # test session initialization

        # no oauth key or secret - error
        with override_settings(HATHITRUST_OAUTH_KEY=None,
                               HATHITRUST_OAUTH_SECRET=None):
            with pytest.raises(ImproperlyConfigured) as excinfo:
                hathi.HathiDataAPI()
            assert 'configuration required' in str(excinfo.value)

        # with oauth key and secret - init oauth
        with override_settings(**self.test_hathi_opts):
            data_api = hathi.HathiDataAPI()
            assert isinstance(data_api.session.auth, requests_oauthlib.OAuth1)
            assert data_api.session.auth.client.client_key == \
                self.test_hathi_key
            assert data_api.session.auth.client.client_secret == \
                self.test_hathi_secret
            assert data_api.session.auth.client.signature_type == 'QUERY'

    @override_settings(**test_hathi_opts)
    def test_get_aggregate(self):
        data_api = hathi.HathiDataAPI()
        htid = 'abc.1235813'

        with patch.object(data_api, '_make_request') as mock_make_request:
            response = data_api.get_aggregate(htid)
            assert response == mock_make_request.return_value
            mock_make_request.assert_called_with('aggregate/%s' % htid,
                                                 params={'v': 2})

    @override_settings(**test_hathi_opts)
    def test_get_structure(self):
        data_api = hathi.HathiDataAPI()
        htid = 'abc.1235813'

        with patch.object(data_api, '_make_request') as mock_make_request:
            response = data_api.get_structure(htid)
            assert response == mock_make_request.return_value
            # default format is xml
            mock_make_request.assert_called_with(
                'structure/%s' % htid, params={'v': 2, 'format': 'xml'})

            response = data_api.get_structure(htid, 'json')
            mock_make_request.assert_called_with(
                'structure/%s' % htid, params={'v': 2, 'format': 'json'})


class TestHathiObject:

    ht_tempdir = tempfile.TemporaryDirectory(prefix="ht_text_pd")

    def test_pairtree_prefix(self):
        hobj = hathi.HathiObject(hathi_id='uva.1234')
        assert hobj.pairtree_prefix == 'uva'

    def test_pairtree_id(self):
        hobj = hathi.HathiObject(hathi_id='uva.1234')
        assert hobj.pairtree_id == '1234'

    def test_content_dir(self):
        hobj = hathi.HathiObject(hathi_id='uva.1234')
        assert hobj.content_dir == pairtree_path.id_encode(hobj.pairtree_id)

    @patch('ppa.archive.hathi.pairtree_client')
    @override_settings(HATHI_DATA=ht_tempdir.name)
    def test_pairtree_object(self, mock_pairtree_client):
        hobj = hathi.HathiObject(hathi_id='uva.1234')

        ptree_obj = hobj.pairtree_object()
        # client initialized
        mock_pairtree_client.PairtreeStorageClient \
            .assert_called_with(hobj.pairtree_prefix,
                                os.path.join(settings.HATHI_DATA, hobj.pairtree_prefix))
        # object retrieved
        mock_pairtree_client.PairtreeStorageClient.return_value \
            .get_object.assert_called_with(hobj.pairtree_id,
                                           create_if_doesnt_exist=False)
        # object returned
        assert ptree_obj == mock_pairtree_client.PairtreeStorageClient  \
                                                .return_value.get_object.return_value

        # test passing in existing pairtree client
        mock_pairtree_client.reset_mock()
        my_ptree_client = Mock(spec=pairtree_client.PairtreeStorageClient)
        ptree_obj = hobj.pairtree_object(my_ptree_client)
        # should not initialize
        mock_pairtree_client.PairtreeStorageClient.assert_not_called()
        # should get object from my client
        my_ptree_client.get_object.assert_called_with(hobj.pairtree_id,
                                                      create_if_doesnt_exist=False)

    @override_settings(HATHI_DATA=ht_tempdir.name)
    def test_zipfile_path(self):
        hobj = hathi.HathiObject(hathi_id='chi.79279237')
        contents = ['79279237.mets.xml', '79279237.zip']

        with patch.object(hathi.HathiObject, 'pairtree_object') as mock_ptree_obj_meth:
            mock_ptree_obj = mock_ptree_obj_meth.return_value
            mock_ptree_obj.list_parts.return_value = contents
            mock_ptree_obj.id_to_dirpath.return_value = \
                '%s/chi/pairtree_root/79/27/92/37' % self.ht_tempdir.name

            zipfile_path = hobj.zipfile_path()
            mock_ptree_obj_meth.assert_called_with(ptree_client=None)
            assert zipfile_path == \
                os.path.join(mock_ptree_obj.id_to_dirpath(), hobj.content_dir,
                             contents[1])

            # use pairtree client object if passed in
            my_ptree_client = Mock(spec=pairtree_client.PairtreeStorageClient)
            hobj.zipfile_path(my_ptree_client)
            mock_ptree_obj_meth.assert_called_with(ptree_client=my_ptree_client)

    @override_settings(HATHI_DATA=ht_tempdir.name)
    def test_metsfile_path(self):
        hobj = hathi.HathiObject(hathi_id='chi.79279237')
        contents = ['79279237.mets.xml', '79279237.zip']

        with patch.object(hathi.HathiObject, 'pairtree_object') as mock_ptree_obj_meth:
            mock_ptree_obj = mock_ptree_obj_meth.return_value
            mock_ptree_obj.list_parts.return_value = contents
            mock_ptree_obj.id_to_dirpath.return_value = \
                '%s/chi/pairtree_root/79/27/92/37' % self.ht_tempdir.name

            metsfile_path = hobj.metsfile_path()
            mock_ptree_obj_meth.assert_called_with(ptree_client=None)
            assert metsfile_path == \
                os.path.join(mock_ptree_obj.id_to_dirpath(), hobj.content_dir,
                             contents[0])

            # use pairtree client object if passed in
            my_ptree_client = Mock(spec=pairtree_client.PairtreeStorageClient)
            hobj.metsfile_path(my_ptree_client)
            mock_ptree_obj_meth.assert_called_with(ptree_client=my_ptree_client)

    def test_delete_pairtree_data(self):
        hobj = hathi.HathiObject(hathi_id='chi.79279237')
        with patch.object(hobj, 'pairtree_client') as mock_pairtree_client:
            hobj.delete_pairtree_data()
            # should initialize client
            mock_pairtree_client.assert_called()
            # should call delete boject
            mock_pairtree_client.return_value.delete_object \
                .assert_called_with(hobj.pairtree_id)

            # should not raise an exception if deletion fails
            mock_pairtree_client.return_value.delete_object.side_effect \
                 = storage_exceptions.ObjectNotFoundException
            hobj.delete_pairtree_data()
            # not currently testing that warning is logged
