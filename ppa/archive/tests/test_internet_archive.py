"""Tests for ppa.archive.internet_archive"""
import json
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests
from django.test import TestCase, override_settings

from ppa import __version__
from ppa.archive import internet_archive as ia_module
from ppa.archive.internet_archive import (
    IAError,
    IAItemNotFound,
    IANoFullText,
    InternetArchiveAPI,
    _is_valid_ia_id,
)


# ---------------------------------------------------------------------------
# _is_valid_ia_id
# ---------------------------------------------------------------------------


def test_is_valid_ia_id_valid():
    assert _is_valid_ia_id("gutenberg-1234")
    assert _is_valid_ia_id("TheProdigalGuest1905")
    assert _is_valid_ia_id("my_book.vol1")


def test_is_valid_ia_id_empty():
    assert not _is_valid_ia_id("")
    assert not _is_valid_ia_id(None)


def test_is_valid_ia_id_too_long():
    assert not _is_valid_ia_id("a" * 81)


def test_is_valid_ia_id_invalid_chars():
    assert not _is_valid_ia_id("has space")
    assert not _is_valid_ia_id("has/slash")
    assert not _is_valid_ia_id("has@symbol")


# ---------------------------------------------------------------------------
# InternetArchiveAPI
# ---------------------------------------------------------------------------


@patch("ppa.archive.internet_archive.requests")
class TestInternetArchiveAPI(TestCase):
    def _make_api(self, mockrequests):
        """Construct an API instance with a mocked session."""
        mockrequests.Session.return_value.headers = {"User-Agent": "requests/1.0"}
        return InternetArchiveAPI()

    def test_init_user_agent(self, mockrequests):
        api = self._make_api(mockrequests)
        assert "ppa-django" in api.session.headers["User-Agent"]
        assert __version__ in api.session.headers["User-Agent"]

    @override_settings(TECHNICAL_CONTACT="admin@example.com")
    def test_init_technical_contact(self, mockrequests):
        api = self._make_api(mockrequests)
        assert api.session.headers["From"] == "admin@example.com"

    @override_settings(IA_ACCESS_KEY="mykey", IA_SECRET_KEY="mysecret")
    def test_init_s3_credentials(self, mockrequests):
        api = self._make_api(mockrequests)
        assert "LOW mykey:mysecret" in api.session.headers["authorization"]

    def test_get_metadata_success(self, mockrequests):
        api = self._make_api(mockrequests)
        mockrequests.codes = requests.codes
        mock_resp = Mock()
        mock_resp.status_code = requests.codes.ok
        mock_resp.json.return_value = {"metadata": {"title": "Test Book"}, "files": []}
        api.session.get.return_value = mock_resp

        result = api.get_metadata("gutenberg-1234")
        assert result["metadata"]["title"] == "Test Book"
        api.session.get.assert_called_once()
        call_url = api.session.get.call_args[0][0]
        assert "gutenberg-1234" in call_url

    def test_get_metadata_not_found_http_404(self, mockrequests):
        api = self._make_api(mockrequests)
        mockrequests.codes = requests.codes
        mock_resp = Mock()
        mock_resp.status_code = requests.codes.not_found
        api.session.get.return_value = mock_resp

        with pytest.raises(IAItemNotFound):
            api.get_metadata("nonexistent-item")

    def test_get_metadata_empty_response(self, mockrequests):
        """IA returns {} for identifiers that don't exist (HTTP 200 but empty body)."""
        api = self._make_api(mockrequests)
        mockrequests.codes = requests.codes
        mock_resp = Mock()
        mock_resp.status_code = requests.codes.ok
        mock_resp.json.return_value = {}
        api.session.get.return_value = mock_resp

        with pytest.raises(IAItemNotFound):
            api.get_metadata("ghost-id")

    def test_get_fulltext_filename_prefers_djvu(self, mockrequests):
        api = self._make_api(mockrequests)
        files = [
            {"name": "item_djvu.xml"},
            {"name": "item_hocr.html"},
            {"name": "item.txt"},
        ]
        assert api.get_fulltext_filename(files) == "item_djvu.xml"

    def test_get_fulltext_filename_hocr_fallback(self, mockrequests):
        api = self._make_api(mockrequests)
        files = [
            {"name": "item_hocr.html"},
            {"name": "item.txt"},
        ]
        assert api.get_fulltext_filename(files) == "item_hocr.html"

    def test_get_fulltext_filename_plain_fallback(self, mockrequests):
        api = self._make_api(mockrequests)
        files = [{"name": "item.txt"}]
        assert api.get_fulltext_filename(files) == "item.txt"

    def test_get_fulltext_filename_none(self, mockrequests):
        api = self._make_api(mockrequests)
        files = [{"name": "item.pdf"}, {"name": "item.mp3"}]
        assert api.get_fulltext_filename(files) is None

    def test_get_item_pages_raises_no_fulltext(self, mockrequests):
        api = self._make_api(mockrequests)
        ia_metadata = {"files": [{"name": "item.pdf"}]}
        with pytest.raises(IANoFullText):
            list(api.get_item_pages("some-id", ia_metadata=ia_metadata))

    def test_pages_from_plaintext(self, mockrequests):
        api = self._make_api(mockrequests)
        mock_resp = Mock()
        mock_resp.text = "Hello world"
        mock_resp.raise_for_status = Mock()
        api.session.get.return_value = mock_resp

        pages = list(api._pages_from_plaintext("test-id", "test.txt"))
        assert len(pages) == 1
        assert pages[0]["content"] == "Hello world"
        assert pages[0]["page_id"] == "p1"

    def test_pages_from_djvu(self, mockrequests):
        api = self._make_api(mockrequests)
        djvu_xml = """<DjVuXML>
          <BODY>
            <PAGE number="1">
              <WORD>Hello</WORD>
              <WORD>world</WORD>
            </PAGE>
            <PAGE number="2">
              <WORD>Page</WORD>
              <WORD>two</WORD>
            </PAGE>
          </BODY>
        </DjVuXML>"""
        mock_resp = Mock()
        mock_resp.text = djvu_xml
        mock_resp.raise_for_status = Mock()
        api.session.get.return_value = mock_resp

        pages = list(api._pages_from_djvu("test-id", "test_djvu.xml"))
        assert len(pages) == 2
        assert pages[0]["page_id"] == "p1"
        assert "Hello" in pages[0]["content"]
        assert pages[1]["page_id"] == "p2"

    def test_pages_from_hocr(self, mockrequests):
        api = self._make_api(mockrequests)
        hocr_html = """<html><body>
          <div class="ocr_page" title="ppageno 0; bbox 0 0 800 1000">
            <span class="ocrx_word">Hello</span>
            <span class="ocrx_word">world</span>
          </div>
          <div class="ocr_page" title="ppageno 1; bbox 0 0 800 1000">
            <span class="ocrx_word">Second</span>
          </div>
        </body></html>"""
        mock_resp = Mock()
        mock_resp.text = hocr_html
        mock_resp.raise_for_status = Mock()
        api.session.get.return_value = mock_resp

        pages = list(api._pages_from_hocr("test-id", "test_hocr.html"))
        assert len(pages) == 2
        assert "Hello" in pages[0]["content"]

    def test_pages_from_plaintext_empty(self, mockrequests):
        """Empty text file yields a page with content=None."""
        api = self._make_api(mockrequests)
        mock_resp = Mock()
        mock_resp.text = "   "
        mock_resp.raise_for_status = Mock()
        api.session.get.return_value = mock_resp

        pages = list(api._pages_from_plaintext("test-id", "empty.txt"))
        assert pages[0]["content"] is None


# ---------------------------------------------------------------------------
# parse_metadata
# ---------------------------------------------------------------------------


def test_parse_metadata_basic():
    raw = {
        "metadata": {
            "title": "My Book",
            "creator": "Smith, John",
            "date": "1905-01-01",
            "publisher": "London Press",
            "language": "English",
        }
    }
    result = InternetArchiveAPI.parse_metadata(raw)
    assert result["title"] == "My Book"
    assert result["author"] == "Smith, John"
    assert result["pub_date"] == 1905
    assert result["publisher"] == "London Press"
    assert result["language"] == "English"


def test_parse_metadata_list_fields():
    """IA often returns lists instead of strings for some metadata fields."""
    raw = {
        "metadata": {
            "title": ["Title One", "Title Two"],
            "creator": ["Author A", "Author B"],
            "date": ["1920"],
        }
    }
    result = InternetArchiveAPI.parse_metadata(raw)
    assert result["title"] == "Title One"
    assert "Author A" in result["author"]
    assert result["pub_date"] == 1920


def test_parse_metadata_missing_fields():
    """Handles items with minimal metadata gracefully."""
    result = InternetArchiveAPI.parse_metadata({"metadata": {}})
    assert result["title"] == ""
    assert result["pub_date"] is None


def test_parse_metadata_year_extraction():
    """Extracts 4-digit year from various date formats."""
    raw = {"metadata": {"date": "19th century (1850-1899)"}}
    # Only first 4-digit token is extracted: "1850"
    result = InternetArchiveAPI.parse_metadata(raw)
    assert result["pub_date"] == 1850


def test_parse_metadata_non_numeric_date():
    raw = {"metadata": {"date": "undated"}}
    result = InternetArchiveAPI.parse_metadata(raw)
    assert result["pub_date"] is None
