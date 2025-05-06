import os.path
import types

from django.test import override_settings
from neuxml.xmlmap import load_xmlobject_from_file, load_xmlobject_from_string

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


# ruff: noqa: E501
# sample xml pages with notes (minimal wrapping tags to load as a text)
PAGE_WITH_NOTE = """<ETS><EEBO><TEXT><PB N="257" REF="198"/><LG>
<L>Whom Monarchs like domestick Slaves obey'd,</L>
<L>On the bleak Shoar now lies th' abandon'd King,</L>
<L N="765"><NOTE N="✓" PLACE="foot"><HI>This whole line is taken from Sir</HI> John Derhan.</NOTE> A headless Carcass, and a nameless thing.</L>
</LG></TEXT></EEBO></ETS>"""
PAGE_WITH_MULTIPLE_NOTES = """<ETS><EEBO><TEXT><P><PB N="3" REF="11"/>
many Colonies. But now the several Languages that are used in the 
world do farre exceed this number.<NOTE PLACE="marg">Nat. Hist. lib. 6. cap. 5. <HI>Strabo,</HI> lib. 11.</NOTE> 
<HI>Pliny</HI> and <HI>Strabo</HI> do both make mention of a great Mart-Town 
in <HI>Colchos</HI> named <HI>Dioscuria,</HI> to which men of three hundred 
Nations, and of so many several Languages, were wont to resort for Trading. 
Which, considering the narrow compass of Traf∣fick before the invention of 
the magnetic Needle, must needs be but a small proportion, in comparison 
to those many of the remoter and un∣known parts of the world.</P>
<P>Some of the <HI>American</HI> Histories relate,<NOTE PLACE="marg">Mr. <HI>Cambden</HI>'s Remains.</NOTE> that in every
 fourscore miles of that vast Country, and almost in every particular
  valley of <HI>Peru,</HI> the Inhabitants have a distinct Language. 
  And one who for several years travelled the Northern parts of 
  <HI>America</HI> about <HI>Florida,</HI>
  <NOTE PLACE="marg"><HI>Purchas</HI> Pilg. lib. 8. sect. 4. chap. 1.</NOTE> 
  and could speak six several Languages of those people, doth affirm, that 
  he found, upon his enquiry and converse with them, more than a thousand 
  different Lan∣guages amongst them.</P>
<P>As for those Languages which seem to have no derivation from, or 
de∣pendance upon, or affinity with one another,<NOTE PLACE="marg">§. III.</NOTE> 
they are styled <HI>Linguae ma∣trices,</HI> or <HI>Mother-tongues.</HI> 
Of these <HI>Ioseph Scaliger</HI> affirms there are ele∣ven, and not more, 
used in <HI>Europe</HI>;<NOTE PLACE="marg">Diatribe de Europaeorum linguis.</NOTE> whereof 
four are of more general and large extent, and the 
other seven of a narrower compass and use. Of the more general Tongues.</P>
</TEXT></EEBO></ETS>"""


def test_parent_note():
    text = load_xmlobject_from_string(PAGE_WITH_MULTIPLE_NOTES, eebo_tcp.Text)
    page = text.pages[0]
    # text directly inside a note tag (note is parent)
    diatribe_note_text = text.node.xpath("//NOTE[contains(., 'Diatribe')]/text()")[0]
    assert page.parent_note(diatribe_note_text) is not None
    # text nested under a tag within a note tag (note is ancestor)
    camden_note_text = text.node.xpath("//NOTE/HI[contains(., 'Cambden')]/text()")[0]
    assert page.parent_note(camden_note_text) is not None
    # text in a tag that is NOT inside a note tag (note is not parent/ancestor)
    europe_hi_text = text.node.xpath("//HI[contains(., 'Europe')]/text()")[0]
    assert page.parent_note(europe_hi_text) is None


def test_get_note_mark():
    text = load_xmlobject_from_string(PAGE_WITH_NOTE, eebo_tcp.Text)
    page = text.pages[0]
    # lower indexes should map exactly
    assert page.get_note_mark(0) == "*"
    assert page.get_note_mark(1) == "†"
    assert page.get_note_mark(2) == "‡"
    assert page.get_note_mark(3) == "§"
    # when index goes past number of available 'marks, repeat the mark
    assert page.get_note_mark(4) == "**"
    assert page.get_note_mark(5) == "††"
    assert page.get_note_mark(8) == "***"


def test_eebo_tcp_page_contents_notes():
    # test that notes are placed at the end of the text instead of inline
    text = load_xmlobject_from_string(PAGE_WITH_NOTE, eebo_tcp.Text)
    page_contents = str(text.pages[0])
    # should not display note contents inline
    assert "taken from Sir John Derhan. A headless Carcass," not in page_contents
    # should display a note marker inline using note marker from the xml
    assert "✓ A headless Carcass" in page_contents
    # should display note contents with marker at end of content
    assert page_contents.endswith("✓ This whole line is taken from Sir John Derhan.")

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


# test quoted poetry & line group logic

LG_EEBO_TCP_FIXTURE_ID = "A45116"
LG_TCP_FIXTURE = os.path.join(FIXTURES_PATH, f"{LG_EEBO_TCP_FIXTURE_ID}.P4.xml")
ECCO_TCP_FIXTURE_ID = "CW0115281335"
ECCO_TCP_FIXTURE = os.path.join(FIXTURES_PATH, f"{ECCO_TCP_FIXTURE_ID}.xml")


@override_settings(EEBO_DATA=FIXTURES_PATH)
def test_text_quotedpoems():
    # first fixture has no Q/LG tags but does have Q/L
    tcp_text = load_xmlobject_from_file(TCP_FIXTURE, eebo_tcp.Text)
    assert len(tcp_text.quoted_poems) == 72
    # fixture with known poetry has 72 quoted poems, 129 linegroups
    lg_tcp_text = load_xmlobject_from_file(LG_TCP_FIXTURE, eebo_tcp.Text)
    assert len(lg_tcp_text.quoted_poems) == 751


@override_settings(ECCO_TCP_DATA=FIXTURES_PATH)
def test_ecco_text_quotedpoems():
    # ecco-tcp fixture has 12 quoted poetry excerpts
    tcp_text = load_xmlobject_from_file(ECCO_TCP_FIXTURE, eebo_tcp.Text)
    assert len(tcp_text.quoted_poems) == 12


@override_settings(EEBO_DATA=FIXTURES_PATH)
def test_quotedpoem_init():
    lg_text = load_xmlobject_from_file(LG_TCP_FIXTURE, eebo_tcp.Text)
    # second quoted poetry lines: Begin then, O my dearest, sacred Dame,
    qpoem = lg_text.quoted_poems[1]
    assert isinstance(qpoem, eebo_tcp.QuotedPoem)
    # should have access to preceding PB as a page object
    # immediately preceding <PB> should be n=2 ref=3
    assert isinstance(qpoem.start_page, eebo_tcp.Page)
    assert qpoem.start_page.number == "2"
    assert qpoem.start_page.ref == "3"
    # this one has no continue page
    assert not qpoem.continue_page
    assert (
        qpoem.text
        == """Begin then, O my dearest, sacred Dame,
Daughter of Phoebus and of Memory,
That dost Ennoble, with Immortal Name,
The Warlike Worthies of Antiquity,
In thy great Volume of Eternity.
Begin, O Clio, &c. Spen. B. 3. C. 3."""
    )


@override_settings(ECCO_TCP_DATA=FIXTURES_PATH)
def test_ecco_quotedpoem_init():
    tcp_text = load_xmlobject_from_file(ECCO_TCP_FIXTURE, eebo_tcp.Text)
    qpoem = tcp_text.quoted_poems[0]
    assert isinstance(qpoem.start_page, eebo_tcp.Page)
    assert qpoem.start_page.number == "viii"
    assert qpoem.start_page.index == 7
    assert qpoem.start_page.ref is None
    assert qpoem.start_page.facsimile == "tcp:0771900501:7"
    # this one has no continue page
    assert not qpoem.continue_page
    # markup / indentation is introducing a lot of extra whitespace;
    # ignore for now and test that we have the text content we want
    expected_text = '''" For Conſcience, like a fiery horſe,
" Will ſtumble, if you check his courſe:
" But ride him with an eaſy rein,
" And rub him down with worldly gain,
" He'll carry you through thick and thin,
" Safe, although dirty, to your inn."'''
    expected_lines = expected_text.split("\n")
    for line in expected_lines:
        assert line in qpoem.text
    assert qpoem.text.strip().startswith(expected_lines[0])
    assert qpoem.text.strip().endswith(expected_lines[-1])


# example ecco-tcp poem with bibliographic note
ecco_quotedpoem_bibl = """<q xmlns="http://www.tei-c.org/ns/1.0">
  <sp>
     <speaker>Queen.</speaker>
     <l>What, is my Richard both in ſhape and mind</l>
     <l>Transform'd and weak? Hath Bolingbroke de<g ref="char:EOLhyphen"/>pos'd</l>
     <l>Thine intellect? Hath he been in thy heart?</l>
     <l>The lion, dying, thruſteth forth his paw,</l>
     <l>And wounds the earth, if nothing elſe, with rage</l>
     <l>To be o'erpower'd: and wilt thou, pupil-like,</l>
     <l>Take thy correction mildly, kiſs the rod,</l>
     <l>And fawn on rage with baſe humility?</l>
  </sp>
  <bibl>Richard II. act 5. ſc. 1.</bibl>
</q>"""


def test_ecco_quotedpoem_bibl():
    # ecco-tcp fixture has 12 quoted poetry excerpts
    qpoem = load_xmlobject_from_string(ecco_quotedpoem_bibl, eebo_tcp.QuotedPoem)
    # can access the citation
    assert qpoem.source == "Richard II. act 5. ſc. 1."
    # citation not included in poem text
    print(qpoem.text_by_page())
    assert qpoem.source not in qpoem.text_by_page()


@override_settings(EEBO_DATA=FIXTURES_PATH)
def test_quotedpoem_has_text():
    lg_text = load_xmlobject_from_file(LG_TCP_FIXTURE, eebo_tcp.Text)
    # first quoted poem is gap  / foreign language : commas + whitespace only
    assert not lg_text.quoted_poems[0].has_text()
    # second qouted poem has text
    assert lg_text.quoted_poems[1].has_text()


@override_settings(EEBO_DATA=FIXTURES_PATH)
def test_quotedpoem_text_by_page():
    lg_text = load_xmlobject_from_file(LG_TCP_FIXTURE, eebo_tcp.Text)
    # quoted poem at index 55 has a q before <pb> and then <l> after
    qpoem = lg_text.quoted_poems[55]
    text_chunks = list(qpoem.text_by_page())

    # there is an empty chunk before the page break
    assert text_chunks[0] == ""
    # then the lines of poetry
    assert (
        text_chunks[1]
        == """
Et Gemina Auratus Taurino Cornua vultu
Eridanus. Georg. 4.
Et sic Tauriformis volvitur Aufidus
Cum saevit, horrendamque cultis
Diluviem Meditatur agris. Hor. Car. Lib. 4. Od. 14."""
    )

    # first quoted poem is gap / foreign and punctuation only; empty if excluded
    assert list(lg_text.quoted_poems[0].text_by_page(include_large_gaps=False)) == [""]
    # test including them
    assert list(lg_text.quoted_poems[0].text_by_page()) == [
        """〈 in non-Latin alphabet 〉.
〈 in non-Latin alphabet 〉."""
    ]


# example ecco-tcp poem with gap for missing letter
ecco_quotedpoem_gap = """<q xmlns="http://www.tei-c.org/ns/1.0">
  <l>Interea magno miſceri murmure pontum</l>
  <l>Emiſſamque hyemem ſenſit Neptunus, et imis</l>
  <l>Stagna refuſa vadis: <hi>graviter commotu<gap reason="illegible" resp="#OXF" extent="1 letter">
           <desc>•</desc>
        </gap>,</hi> et alto</l>
  <l>Proſpiciens, ſummâ <hi>placidum</hi> caput extulit undâ.</l>
  <bibl>Aeneid. i. 128.</bibl>
</q>"""


def test_quotedpoem_text_by_page_p5_gap():
    qpoem = load_xmlobject_from_string(ecco_quotedpoem_gap, eebo_tcp.QuotedPoem)
    text = list(qpoem.text_by_page())[0]
    # desc character should be included without surrounding whitespace
    assert "Stagna refuſa vadis: graviter commotu•, et alto" in text


@override_settings(EEBO_DATA=FIXTURES_PATH)
def test_quotedpoem_multipage():
    lg_text = load_xmlobject_from_file(LG_TCP_FIXTURE, eebo_tcp.Text)
    multipage_poems = []
    singlepage_poems = []
    for i, qp in enumerate(lg_text.quoted_poems):
        if qp.continue_page:
            multipage_poems.append(i)
        else:
            singlepage_poems.append(i)
    # check singlepage poems identified
    assert all(n_poem in singlepage_poems for n_poem in [0, 1, 2, 3])
    # check some multipage poems identified
    assert all(n_poem in multipage_poems for n_poem in [44, 55, 62, 84, 111])


@override_settings(EEBO_DATA=FIXTURES_PATH)
def test_linegroup_init():
    lg_text = load_xmlobject_from_file(LG_TCP_FIXTURE, eebo_tcp.Text)
    # second line group in 12th quoted poem: Tum Tartarus ipse
    linegroup = lg_text.quoted_poems[11].line_groups[1]
    assert isinstance(linegroup, eebo_tcp.LineGroup)
    # text content: multiline, with newlines between/before/after tags
    assert (
        linegroup.text
        == """\nTum Tartarus ipse,
Bis patet in praeceps tantum, tenditque sub umbras;
Quantus ad AEthereum Coeli suspectus Olympum. AEn. 6.\n"""
    )

    # this one also has no source/heading and no language tag
    # (even though it's in Latin)
    assert not linegroup.source
    assert not linegroup.language

    # first line group in this quoted poem has no content
    assert not lg_text.quoted_poems[11].line_groups[0].has_text()
