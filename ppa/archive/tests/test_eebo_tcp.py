import os.path
import types

from django.test import override_settings
from eulxml.xmlmap import load_xmlobject_from_file

from ppa.archive import eebo_tcp
from ppa.archive.tests.test_models import FIXTURES_PATH


EEBO_TCP_FIXTURE_ID = "A25820"
TCP_FIXTURE = os.path.join(FIXTURES_PATH, f"{EEBO_TCP_FIXTURE_ID}.P4.xml")


def test_eebo_tcp_page_contents():
    tcp_text = load_xmlobject_from_file(TCP_FIXTURE, eebo_tcp.Text)

    # text after second pb ref=5
    page_ref5_content = str(tcp_text.pages[9])
    assert page_ref5_content.startswith("\nof Words, as in a Picture,")
    assert page_ref5_content.endswith("Nature of things: Which is the True\n")
    # divider character should be removed
    assert "Instituti∣ons" not in page_ref5_content
    assert "Institutions" in page_ref5_content

    # text after second pb ref=6
    page_ref6_content = str(tcp_text.pages[11])
    assert page_ref6_content.startswith("\nIn conforming to the Auditory there is more")
    assert page_ref6_content.endswith("applaud Hercules, among\n")
    # gap display character included (for now)
    assert "speak in •raise" in page_ref6_content

    # test the last page
    last_page_content = str(tcp_text.pages[-1])
    assert last_page_content.startswith("CHAP. XXI. Of Repetition. 256")
    # we get extra newlines because of the containing elemnts; ignore for testing
    assert last_page_content.rstrip().endswith(
        "CHAP. XXXVIII. The Peroration. 258\nFINIS."
    )


def test_short_id():
    assert eebo_tcp.short_id("A25820.0001.001") == "A25820"
    assert eebo_tcp.short_id("A25820") == "A25820"


def test_page_object():
    tcp_text = load_xmlobject_from_file(TCP_FIXTURE, eebo_tcp.Text)
    assert isinstance(tcp_text.pages[0], eebo_tcp.Page)
    assert tcp_text.pages[0].ref == "1"
    assert tcp_text.pages[0].number is None
    assert repr(tcp_text.pages[0]) == "<Page - (license)>"

    # test a numbered page
    assert tcp_text.pages[13].ref == "7"
    assert tcp_text.pages[13].number == "1"
    assert repr(tcp_text.pages[13]) == "<Page 1 (book)>"


@override_settings(EEBO_DATA=FIXTURES_PATH)
def test_page_count():
    assert eebo_tcp.page_count(EEBO_TCP_FIXTURE_ID) == 300


@override_settings(EEBO_DATA=FIXTURES_PATH)
def test_page_data():
    page_info = eebo_tcp.page_data(EEBO_TCP_FIXTURE_ID)
    assert isinstance(page_info, types.GeneratorType)
    page_info = list(page_info)
    assert len(page_info) == 300

    # inspect a couple of pages
    assert page_info[0]["label"] is None
    assert "Licensed,\nROBERT MIDGLEY." in page_info[0]["content"]
    assert page_info[0]["tags"] == ["license"]
    # page with a page number
    assert page_info[13]["label"] == "1"
