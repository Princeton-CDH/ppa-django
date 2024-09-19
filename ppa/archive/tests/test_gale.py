import os.path
from unittest.mock import Mock, patch

import pytest
import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from ppa import __version__
from ppa.archive import gale
from ppa.archive.tests.test_models import FIXTURES_PATH


@override_settings()
def test_get_local_ocr(tmp_path):
    item_id = "CB0123456789"
    page_num = "0001"
    content = "Testing...\n1\n2\n3"
    # Mock ocr files for testing
    ocr_dir = tmp_path.joinpath("146", item_id)
    ocr_dir.mkdir(parents=True)
    ocr_file = ocr_dir.joinpath(f"{item_id}_{page_num}0.txt")
    ocr_file.write_text(content)

    with override_settings(GALE_LOCAL_OCR=f"{tmp_path}"):
        assert content == gale.get_local_ocr(item_id, page_num)


@override_settings()
def test_get_local_ocr_config_error():
    del settings.GALE_LOCAL_OCR
    with pytest.raises(ImproperlyConfigured):
        gale.get_local_ocr("item_id", "page_num")


@override_settings(GALE_API_USERNAME="galeuser123")
@patch("ppa.archive.gale.requests")
class TestGaleAPI(TestCase):
    # NOTE: must extend django's test case to use override_settings on class

    def test_new(self, mockrequests):
        # test singleton behavior;
        # initializing multiple times should return the same instance
        gale_api = gale.GaleAPI()
        assert gale_api == gale.GaleAPI()

    def test_init(self, mockrequests):
        # test session initialization

        # no technical contact
        with override_settings(TECHNICAL_CONTACT=None):
            base_user_agent = "requests/v123"
            mockrequests.Session.return_value.headers = {"User-Agent": base_user_agent}
            gale_api = gale.GaleAPI()
            mockrequests.Session.assert_any_call()
            assert gale_api.session == mockrequests.Session.return_value
            assert "ppa-django" in gale_api.session.headers["User-Agent"]
            assert __version__ in gale_api.session.headers["User-Agent"]
            assert "(%s)" % base_user_agent in gale_api.session.headers["User-Agent"]
            assert "From" not in gale_api.session.headers

        # technical contact configured
        tech_contact = "webmaster@example.com"
        with override_settings(TECHNICAL_CONTACT=tech_contact):
            gale_api = gale.GaleAPI()
            assert gale_api.session.headers["From"] == tech_contact

    @override_settings()
    def test_config_error(self, mockrequests):
        del settings.GALE_API_USERNAME
        with pytest.raises(ImproperlyConfigured):
            gale.GaleAPI()

    def test_make_request(self, mockrequests):
        gale_api = gale.GaleAPI()
        gale_api.api_root = "http://example.com/api"
        mockrequests.codes = requests.codes

        # mock successful request (no streaming or api key)
        gale_api.session.get.return_value.status_code = requests.codes.ok
        resp = gale_api._make_request("foo", requires_api_key=False)
        gale_api.session.get.assert_called_with(
            "%s/foo" % gale_api.api_root, stream=False
        )
        assert resp == gale_api.session.get.return_value
        # with streaming option
        gale_api._make_request("foo", requires_api_key=False, stream=True)
        gale_api.session.get.assert_called_with(
            "%s/foo" % gale_api.api_root, stream=True
        )
        # request with api key
        gale_api._api_key = "testkey"  # set a test api key
        gale_api._make_request("foo")
        gale_api.session.get.assert_called_with(
            "%s/foo" % gale_api.api_root, stream=False, params={"api_key": "testkey"}
        )

        # 404 not found response should raise item not found
        gale_api.session.get.return_value.status_code = requests.codes.not_found
        with pytest.raises(gale.GaleItemNotFound):
            gale_api._make_request("foo")

        # 403 forbidden response should raise item forbidden
        gale_api.session.get.return_value.status_code = requests.codes.forbidden
        with pytest.raises(gale.GaleItemForbidden):
            gale_api._make_request("foo")

    @patch("ppa.archive.gale.GaleAPI.get_api_key")
    def test_make_request_refresh_key(self, mock_get_api_key, mockrequests):
        # test retrying request when api key has expired
        gale_api = gale.GaleAPI()
        gale_api._api_key = None  # make sure unset for this test
        gale_api.api_root = "http://example.com/api"
        mockrequests.codes = requests.codes
        mock_get_api_key.side_effect = ("testkey1", "testkey2", "testkey3", "testkey4")

        # return 401 unauthorized the first time; 200 ok the second
        # logging requires numeric elapsed seconds
        unauth_response = Mock(status_code=requests.codes.unauthorized)
        unauth_response.elapsed.total_seconds.return_value = 1
        ok_response = Mock(status_code=requests.codes.ok)
        ok_response.elapsed.total_seconds.return_value = 3

        gale_api.session.get.side_effect = [unauth_response, ok_response]
        resp = gale_api._make_request("foo", requires_api_key=True)
        # should be called twice: once for initial request, then for retry
        assert mock_get_api_key.call_count == 2
        gale_api.session.get.assert_any_call(
            "%s/foo" % gale_api.api_root, params={"api_key": "testkey1"}, stream=False
        )
        # same request but with the new key
        gale_api.session.get.assert_any_call(
            "%s/foo" % gale_api.api_root, params={"api_key": "testkey2"}, stream=False
        )

        # retry should preserve parameters and streaming option
        gale_api.session.reset_mock()
        gale_api.session.get.side_effect = [unauth_response, ok_response]
        resp = gale_api._make_request(
            "foo", params={"bar": "baz"}, stream=True, requires_api_key=True
        )
        gale_api.session.get.assert_any_call(
            "%s/foo" % gale_api.api_root,
            params={"api_key": "testkey2", "bar": "baz"},
            stream=True,
        )
        # same request but with the new key
        gale_api.session.get.assert_any_call(
            "%s/foo" % gale_api.api_root,
            params={"api_key": "testkey3", "bar": "baz"},
            stream=True,
        )

        # ** test cases where retry should not happen

        # request that does not require api key
        mock_get_api_key.reset_mock()
        gale_api.session.reset_mock()
        gale_api.session.get.side_effect = [unauth_response, ok_response]
        with pytest.raises(gale.GaleUnauthorized):
            resp = gale_api._make_request("foo", requires_api_key=False)
        # should not get a new key; should only make the request once
        mock_get_api_key.assert_not_called()
        assert gale_api.session.get.call_count == 1

        # already on a retry (no infinite loops requesting new keys!)
        mock_get_api_key.reset_mock()
        gale_api.session.reset_mock()
        gale_api.session.get.side_effect = [unauth_response, ok_response]
        with pytest.raises(gale.GaleUnauthorized):
            resp = gale_api._make_request("foo", requires_api_key=True, retry=1)
        # should not get a new key; should only make the request once
        mock_get_api_key.assert_not_called()
        assert gale_api.session.get.call_count == 1

    def test_get_api_key(self, mockrequests):
        gale_api = gale.GaleAPI()
        mockrequests.codes = requests.codes
        gale_api.session.get.return_value.status_code = requests.codes.ok
        test_api_key = "12345abcd"
        gale_api.session.get.return_value.json.return_value = {"apiKey": test_api_key}
        assert gale_api.get_api_key() == test_api_key
        gale_api.session.get.assert_called_with(
            "%s/tools/generate_key" % gale_api.api_root,
            stream=False,
            params={"user": "galeuser123"},
        )

    def test_refresh_api_key(self, mockrequests):
        gale_api = gale.GaleAPI()
        gale_api._api_key = None  # make sure unset before testing
        mockrequests.codes = requests.codes
        gale_api.session.get.return_value.status_code = requests.codes.ok
        test_api_key1 = "12345abcd"
        test_api_key2 = "67890ef68"
        gale_api.session.get.return_value.json.side_effect = (
            {"apiKey": test_api_key1},
            {"apiKey": test_api_key2},
        )

        # first request should be api key 1
        assert gale_api.api_key == test_api_key1
        # get again without refreshing — same
        assert gale_api.api_key == test_api_key1
        # after refreswh we should get a new one
        gale_api.refresh_api_key()
        assert gale_api.api_key == test_api_key2

    @patch("ppa.archive.gale.GaleAPI.get_api_key")
    def test_api_key(self, mock_get_api_key, mockrequests):
        gale_api = gale.GaleAPI()
        gale_api._api_key = None  # ensure unset since shared across instances
        test_api_key = "access9876"
        mock_get_api_key.return_value = test_api_key
        assert gale_api.api_key == test_api_key

        # once it is set, should not request a new key from the api again
        mock_get_api_key.reset_mock()
        assert gale_api.api_key == test_api_key
        assert not mock_get_api_key.call_count

    def test_get_item(self, mockrequests):
        gale_api = gale.GaleAPI()
        mockrequests.codes = requests.codes
        gale_api._api_key = "12345abcd"
        # simulate valid request
        gale_api.session.get.return_value.status_code = requests.codes.ok

        item = gale_api.get_item("CW123456")
        gale_api.session.get.assert_called_with(
            "%s/v1/item/GALE%%7CCW123456" % gale_api.api_root,
            stream=True,
            params={"api_key": gale_api.api_key},
        )
        # json response is returned on success
        assert item == gale_api.session.get.return_value.json.return_value

        # simulate invalid request that raises a generic exception
        gale_api.session.get.return_value.status_code = requests.codes.bad_request
        with pytest.raises(gale.GaleAPIError):
            gale_api.get_item("CW123456")

    @patch("ppa.archive.gale.get_local_ocr")
    @patch("ppa.archive.gale.GaleAPI.get_item")
    def test_get_item_pages(self, mock_get_item, mock_get_local_ocr):
        item_id = "CW0123456789"
        # Set up API
        gale_api = gale.GaleAPI()
        test_pages = [
            {
                "pageNumber": "0001",
                "folioNumber": "i",
                "image": {"id": "09876001234567", "url": "http://example.com/img/1"}
                # some pages have no ocr text
            },
            {
                "pageNumber": "0002",
                "image": {"id": "08765002345678", "url": "http://example.com/img/2"},
                "ocrText": "more test content",
            },
            {
                "pageNumber": "0003",
                "image": {"id": "0765400456789", "url": "http://example.com/img/3"},
                "ocrText": "ignored text",
            },
        ]
        api_response = {
            "doc": {},  # unused for this test
            "pageResponse": {"pages": test_pages},
        }
        mock_get_item.return_value = api_response
        # Set up get_local_ocr so that only the 3rd puuuage's text is found
        mock_get_local_ocr.side_effect = [FileNotFoundError, FileNotFoundError, "local ocr text"]
        page_data = list(gale_api.get_item_pages(item_id))
        mock_get_item.called_once()
        assert mock_get_local_ocr.call_count == 3
        assert len(page_data) == 3
        assert [ p["page_id"] for p in page_data ] == ["0001", "0002", "0003"]
        assert [ p["content"] for p in page_data ] == [None, "more test content", "local ocr text"]
        assert [ p["tags"] for p in page_data ] == [ [], [], ["local_ocr"] ]
        assert [ p["image_id_s"] for p in page_data ] == ["09876001234567", "08765002345678", "0765400456789"]
        assert [ p["image_urls_s"] for p in page_data ] == [f"http://example.com/img/{i+1}" for i in range(3)]

        # skip apip call if record is provided
        mock_get_item.reset_mock()
        page_data = list(gale_api.get_item_pages(item_id, api_response))
        mcok_get_item.assert_not_called()
        assert mock_get_local_ocr.call_count == 3
        assert len(page_data) == 3


@override_settings(MARC_DATA="/path/to/data/marc")
@patch("ppa.archive.gale.PairtreeStorageFactory")
def test_get_marc_storage(mock_pairtree_storage_factory):
    mstore = gale.get_marc_storage()
    mock_pairtree_storage_factory.assert_called_with()
    mock_pairtree_storage_factory.return_value.get_store.assert_called_with(
        store_dir=settings.MARC_DATA, uri_base="info:local/"
    )


@patch("ppa.archive.gale.get_marc_storage")
def test_get_marc_record(mock_get_marc_storage):
    test_marc_file = os.path.join(FIXTURES_PATH, "test_marc.dat")
    with open(test_marc_file, "rb") as marcfile:
        ptree_obj = mock_get_marc_storage.return_value.get_object.return_value
        ptree_obj.get_bytestream.return_value.__enter__.return_value = marcfile

        test_id = "CW123456"
        record = gale.get_marc_record(test_id)
        mock_get_marc_storage.assert_called_with()
        mock_get_marc_storage.return_value.get_object.assert_called_with(test_id)
        ptree_obj.get_bytestream.assert_called_with("marc.dat", streamable=True)

        # confirm we loaded the MARC record and can read it
        assert record.title() == "Cross-platform Perl /"
