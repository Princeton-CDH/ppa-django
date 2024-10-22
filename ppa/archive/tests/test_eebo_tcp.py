import os.path
import types

from django.test import override_settings
from eulxml.xmlmap import load_xmlobject_from_file, load_xmlobject_from_string

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


# sample xml pages with notes (minimal wrapping tags to load as a text)
PAGE_WITH_NOTE = """<ETS><EEBO><TEXT><PB N="257" REF="198"/><LG>
<L>Whom Monarchs like domestick Slaves obey'd,</L>
<L>On the bleak Shoar now lies th' abandon'd King,</L>
<L N="765"><NOTE N="*" PLACE="foot"><HI>This whole line is taken from Sir</HI> John Derhan.</NOTE> A headless Carcass, and a nameless thing.</L>
</LG></TEXT></EEBO></ETS>"""
PAGE_WITH_MULTIPLE_NOTES = """<ETS><EEBO><TEXT><P><PB N="3" REF="11"/>
many Colonies. But now the several Languages that are used in the world do farre exceed this number.<NOTE PLACE="marg">Nat. Hist. lib. 6. cap. 5. <HI>Strabo,</HI> lib. 11.</NOTE> <HI>Pliny</HI> and <HI>Strabo</HI> do both make mention of a great Mart-Town in <HI>Colchos</HI> named <HI>Dioscuria,</HI> to which men of three hundred Nations, and of so many several Languages, were wont to resort for Trading. Which, considering the narrow compass of Traf∣fick before the invention of the magnetic Needle, must needs be but a small proportion, in comparison to those many of the remoter and un∣known parts of the world.</P>
<P>Some of the <HI>American</HI> Histories relate,<NOTE PLACE="marg">Mr. <HI>Cambden</HI>'s Remains.</NOTE> that in every fourscore miles of that vast Country, and almost in every particular valley of <HI>Peru,</HI> the Inhabitants have a distinct Language. And one who for several years travelled the Northern parts of <HI>America</HI> about <HI>Florida,</HI><NOTE PLACE="marg"><HI>Purchas</HI> Pilg. lib. 8. sect. 4. chap. 1.</NOTE> and could speak six several Languages of those people, doth affirm, that he found, upon his enquiry and converse with them, more than a thousand different Lan∣guages amongst them.</P>
<P>As for those Languages which seem to have no derivation from, or de∣pendance upon, or affinity with one another,<NOTE PLACE="marg">§. III.</NOTE> they are styled <HI>Linguae ma∣trices,</HI> or <HI>Mother-tongues.</HI> Of these <HI>Ioseph Scaliger</HI>
 affirms there are ele∣ven, and not more, used in <HI>Europe</HI>;<NOTE PLACE="marg">Diatribe de Europaeorum linguis.</NOTE> whereof four are of more general and large extent, and the other seven of a narrower compass and use. Of the more general Tongues
.</P></TEXT></EEBO></ETS>"""


def test_text_inside_note():
    text = load_xmlobject_from_string(PAGE_WITH_MULTIPLE_NOTES, eebo_tcp.Text)
    page = text.pages[0]
    # text directly inside a note tag (note is parent)
    diatribe_note_text = text.node.xpath("//NOTE[contains(., 'Diatribe')]/text()")[0]
    assert page.text_inside_note(diatribe_note_text) is not None
    # text nested under a tag within a note tag (note is ancestor)
    camden_note_text = text.node.xpath("//NOTE/HI[contains(., 'Cambden')]/text()")[0]
    assert page.text_inside_note(camden_note_text)
    # text in a tag that is NOT inside a note tag (note is not parent/ancestor)
    europe_hi_text = text.node.xpath("//HI[contains(., 'Europe')]/text()")[0]
    assert page.text_inside_note(europe_hi_text) is None


def test_eebo_tcp_page_contents_notes():
    # test that notes are placed at the end of the text instead of inline
    text = load_xmlobject_from_string(PAGE_WITH_NOTE, eebo_tcp.Text)
    page_contents = str(text.pages[0])
    # should not display note contents inline
    assert "taken from Sir John Derhan. A headless Carcass," not in page_contents
    # should display a note marker inline
    assert "* A headless Carcass" in page_contents
    # should display note contents with marker at end of content
    assert page_contents.endswith("* This whole line is taken from Sir John Derhan.")

    text = load_xmlobject_from_string(PAGE_WITH_MULTIPLE_NOTES, eebo_tcp.Text)
    page_contents = str(text.pages[0])
    # notes should be displayed with markers in sequence
    # all text within first note should be displayed as a single note, not multiple
    assert "* Nat. Hist. lib. 6. cap. 5. Strabo, lib. 11." in page_contents
    assert "† Mr. Cambden's Remains" in page_contents
    assert "** Diatribe de Europaeorum linguis." in page_contents
    # note markers should be displayed inline where note was located
    assert "exceed this number.*" in page_contents
    assert "Histories relate,† that" in page_contents
    assert "used in Europe;** whereof" in page_contents


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
