"""
Code for working with EEBO-TCP (Text Creation Partnership) content.
"""

from collections import namedtuple
from pathlib import Path
import string

from django.conf import settings
from eulxml import xmlmap


def short_id(volume_id):
    # volume ids in import spreadsheet are in this format: A25820.0001.001
    # TCP records use the first portion only
    return volume_id.split(".")[0]


# P4 TCP TEI does not use namespaces but P5 does
TEI_NAMESPACE = "http://www.tei-c.org/ns/1.0"


# namespaced tags look like {http://www.tei-c.org/ns/1.0}tagname
# create a named tuple of short tag name -> namespaced tag name
_p5_tags = ["bibl", "gap", "pb", "l", "desc", "note"]
TagNames = namedtuple("TagNames", _p5_tags)
P5_TAG = TagNames(**{tag: "{%s}%s" % (TEI_NAMESPACE, tag) for tag in _p5_tags})


class TeiXmlObject(xmlmap.XmlObject):
    ROOT_NAMESPACES = {"t": TEI_NAMESPACE}


class MixedText(TeiXmlObject):
    divider = "∣"

    # count following notes as a quick check to bail out of note detection logic
    # (can't use eulxml boolean field here because it assumes string values for true/false)
    has_notes = xmlmap.IntegerField("count(following::NOTE)")

    def parent_note(self, text):
        """check if a text element occurs within a NOTE element; if so,
        return the note element"""

        # bail out if there are no notes following this page
        if not self.has_notes:
            return None

        # check if this text is directly inside a note tag
        within_note = None
        # check if this is normal text directly inside a note tag
        parent = text.getparent()
        if parent.tag in ["NOTE", P5_TAG.note] and text.is_text:
            within_note = parent
        # otherwise, check if text is nested somewhere under a note tag
        else:
            # get the first/nearest ancestor note, if there is one
            note_ancestors = parent.xpath("ancestor::NOTE[1]")
            within_note = note_ancestors[0] if note_ancestors else None

        return within_note

    def within_bibl(self, text):
        """Check if a text element occurs within a bibliography element (BIBL);
        if so, return the element."""
        # check if this text is directly inside a bibl tag
        within_bibl = None
        # check if this is normal text directly inside a note tag
        parent = text.getparent()
        if parent.tag in ["BIBL", P5_TAG.bibl] and text.is_text:
            within_bibl = parent
        # otherwise, check if text is nested somewhere under a note tag
        else:
            # get the first/nearest ancestor note, if there is one
            # NOTE: skipping p5 version for now - complains about namespace
            bibl_ancestors = parent.xpath("ancestor::BIBL")
            within_bibl = bibl_ancestors[0] if bibl_ancestors else None

        return within_bibl


class Page(MixedText):
    """A page of content in an EEBO-TCP text"""

    #: reference id for image scan (two pages per image)
    ref = xmlmap.StringField("@REF")
    #: source page number (optional)
    number = xmlmap.StringField("@N|@n")
    #: facimile id (TCP P5 only)
    facsimile = xmlmap.StringField("@facs")

    #: page index, based on count of preceding <PB> tags
    index = xmlmap.IntegerField("count(preceding::PB|preceding::t:pb) + 1")

    # parent div type =~ page type / label ?
    section_type = xmlmap.StringField("ancestor::DIV1/@TYPE")

    # page beginning tags delimit content instead of containing it;
    # use following axis to find all text nodes following this page beginning
    text_contents = xmlmap.StringListField("following::text()")

    def __repr__(self):
        return f"<Page {self.number or '-'} ({self.section_type})>"

    # footnote indicators
    note_marks = ["*", "†", "‡", "§"]
    num_note_marks = len(note_marks)

    def get_note_mark(self, i):
        """Generate a note marker based on note index and :attr:`note_marks`;
        symbols are used in order and then doubled, tripled, etc as needed.
        (Fallback, for use when a note does not have an N attribute.)"""

        # use modulo to map to the list of available marks
        mark_index = i % self.num_note_marks
        # use division to determine how many times to repeat the mark
        repeat = int(i / self.num_note_marks) + 1
        return self.note_marks[mark_index] * repeat

    def page_contents(self):
        """generator of text strings between this page beginning tag and
        the next one"""

        # strictly speaking we are returning lxml "smart strings"
        # (lxml.etree._ElementUnicodeResult)

        # collect text content for any notes, to be included
        # after main page text contents
        notes_text = []
        # keep track of note count as we encounter them;
        # used for locally generated footnote marks
        note_index = 0

        # iterate and yield text following the current page
        # break until we hit the next page beginning
        for i, text in enumerate(self.text_contents):
            parent = text.getparent()

            # check if this text falls inside a note tag
            within_note = self.parent_note(text)
            if within_note is not None:
                # is this the first text in this note?
                within_note.xpath(".//text()")
                is_first_text = within_note.xpath(".//text()")[0] == str(text)
                if is_first_text:
                    # if this is the first text for this note,
                    # add a marker inline with the text AND to the note
                    note_mark = within_note.get("N", self.get_note_mark(note_index))
                    yield note_mark
                    notes_text.append(f"{note_mark} ")
                    note_index += 1

                # save note text content to be yielded later
                notes_text.append(text)

                # skip to next loop without yielding text in current context
                continue

            # lxml handles text between elements as "tail" text;
            # the parent of the tail text is the preceding element
            if text.is_tail and parent.tag == "GAP":
                # if text precedes a GAP tag, include the display content
                # from the DISP (for now)
                yield text.getparent().get("DISP")

            if text.is_tail and parent.tag == "PB":
                # the first loop is the first text node in the current page;
                # any iteration after that that comes after a PB
                # is the end of this page
                if i > 0:
                    break

            yield text

        # if this page includes notes, yield notes after main text content
        if notes_text:
            # yield two blank lines to separate main text content from notes
            yield "\n\n"
            yield from notes_text

    def __str__(self):
        # NOTE: P4 EEBO-TCP content uses unicode divider character ∣
        # to indicate page breaks that caused hyphenated words
        # in the original text; remove them
        return "".join(self.page_contents()).replace(self.divider, "")


# we actually probably want quoted poetry
# <Q><L>... - single line or two lines
# or
# <Q><BIBL><LG><l>...</LG>
# - may have multiple line groups; may have translation in parallel (eng/latin) on line group
# lg may have type, e.g. type=sonnet
# but sometimes a Q has multiple line groups with their own BIBL entry...

# sometimes PB is nested but no content before it, e.g. A04254
# <Q><PB REF="49"/>
# L>Out through his cairt, quhair Eous vvas eik</L>
# <L>VVith other thre, quhilk Phaëton had dravvin.</L></Q></P>

# translation table for removing punctuation
rm_punctuation = str.maketrans("", "", string.punctuation)


def has_text(content):
    # check if content has any text, ignoring punctuation and whitespace
    # (in some cases, line groups have only gap tags indicating foreign
    # language with punctuation but no actual text)
    # special case: consider &c. punctuation
    return content.replace("&c.", "").translate(rm_punctuation).strip() != ""


class LineGroup(TeiXmlObject):
    """A group of poetry lines in an EEBO-TCP text"""

    #: language (available for some line groups)
    language = xmlmap.StringField("@LANG|@xml:lang")
    #: citation / bibliography
    source = xmlmap.StringField(
        # in TCP P4 this is sometimes available as BIBL;
        # in P5, preceding head tag may have a label
        "(preceding-sibling::BIBL|preceding-sibling::t:head)[1]"
    )
    text = xmlmap.StringField(".")  # NOTE: doesn't handle gaps; maybe that's fine
    lg_type = xmlmap.StringField("@TYPE")

    def has_text(self):
        return has_text(self.text)


class Note(TeiXmlObject):
    place = xmlmap.StringField("@PLACE")
    text = xmlmap.StringField(".")

    @property
    def label(self):
        if self.place == "marg":
            return "Marginal Note"
        return f"Note {self.place}"

    def __str__(self):
        return self.text.replace(MixedText.divSider, "")


class QuotedPoem(MixedText):
    """Quoted poetry stanzas or lines in an EEBO-TCP text"""

    #: list of line groups (LG), e.g. an entire quoted stanza
    line_groups = xmlmap.NodeListField("LG|t:lg", LineGroup)
    #: lines quoted directly, not within a line group
    # lines = xmlmap.NodeListField("L|t:l", Line)

    #: citation / bibliography
    #: may occur before/after a list of lines, within a linegroup, within a note
    source = xmlmap.StringField(".//BIBL|t:bibl", normalize=True)

    #: number for the immediate preceding page begin tag
    start_page = xmlmap.NodeField("preceding::PB[1]|preceding::t:pb[1]", Page)
    continue_page = xmlmap.NodeField("./PB[1]|./t:pb[1]", Page)

    #: full text of this node; prefer text_by_page
    text = xmlmap.StringField(".")  # NOTE: does not include gaps

    #: all text nodes within this quote, at any depth
    text_contents = xmlmap.StringListField(".//text()")

    #: some records include notes with a citation
    notes = xmlmap.NodeListField("NOTE", Note)

    def has_text(self):
        return has_text(self.text)

    def text_by_page(self, include_large_gaps=True):
        """generator of poetry text chunks per page"""

        # current chunk of text
        current_text = []

        # iterate and yield text following the current page
        # break until we hit the next page beginning
        for i, text in enumerate(self.text_contents):
            parent = text.getparent()

            # omit text anywhere under a bibliography note
            # (may have nested tags like <hi>)
            if self.within_bibl(text) is not None:
                continue

            # check if this text falls inside a note tag
            within_note = self.parent_note(text)
            if within_note is not None:
                # for poem excerpts, don't include note markers or content
                # TODO: exception - if note has an n attribute with a marker, output that
                # Gale/ECCO format seems to be this: (a)

                # NOTE: the fact that we don't output
                # the note marker means that poem excerpts with notes
                # will NOT match ppa page content exactly
                continue

            # lxml handles text between elements as "tail" text;
            # the parent of the tail text is the preceding element
            if text.is_tail and parent.tag == "GAP":
                # if text precedes a GAP tag, include the display content
                # from the DISP.
                # *include* content like: 〈 in non-Latin alphabet 〉
                # so we can more easily filter it out later, unless
                # include_large_gaps is false
                if include_large_gaps or "1 letter" in parent.get("EXTENT", ""):
                    display = parent.get("DISP", None)
                    if display:
                        current_text.append(display)

            # P5: skip text directly within a gap tag
            # (before or after desc tag) to avoid unwanted whitespace
            if (text.is_text and parent.tag == P5_TAG.gap) or (
                text.is_tail and parent.tag == P5_TAG.desc
            ):
                continue

            if text.is_text and parent.tag == P5_TAG.desc:
                # when we hit a desc tag, check the parent gap tag
                # to determine if it should be skipped
                outer_parent = parent.getparent()
                # skip unless we are including large gaps or gap extent
                # is a single letter
                if outer_parent.tag == P5_TAG.gap:
                    if not (
                        include_large_gaps
                        or "1 letter" in outer_parent.get("extent", "")
                    ):
                        continue

            if text.is_tail and parent.tag in ["PB", P5_TAG.pb]:
                # if we hit the text after a page begin tag,
                # yield the previous text and start a new chunk

                chunk = "".join(current_text).replace(self.divider, "")
                # if content is only whitespace and punctuation,
                # yield empty string
                yield chunk if has_text(chunk) else ""

                current_text = []

            # special case: P5 indentation is causing extra whitespace
            # For any text that is only whitespace and starts
            # with a newline, replace with a single newline
            if text.strip() == "" and text.startswith("\n"):
                # replace with regular text - this must be last check
                text = "\n"

            current_text.append(text)

        # yield any remaining text
        # replace page divider character to match ppa page text
        if current_text:
            chunk = "".join(current_text).replace(self.divider, "")
            # if content is only whitespace and punctuation,
            # yield empty string
            yield chunk if has_text(chunk) else ""


class Text(TeiXmlObject):
    """:class:~`eulxml.xmlmap.XmlObject` for extracting page text from
    EEBO-TCP P4 xml or P5 xml"""

    # EEBO-TCP TEI does not use or declare any namespaces

    # pages are delimited by page beginning tags, which may occur at
    # various levels nested within divs, paragraphs, etc

    #: list of page objects, identified by page beginning tag (PB)
    pages = xmlmap.NodeListField("EEBO//TEXT//PB|.//t:text//t:pb", Page)
    #: list of quoted poems, identified by Q that contains LG or L
    quoted_poems = xmlmap.NodeListField(
        "EEBO//TEXT//Q[LG or L]|.//t:text//t:q[t:lg or t:l]", QuotedPoem
    )


def load_tcp_text(volume_id):
    xml_path = Path(settings.EEBO_DATA) / f"{short_id(volume_id)}.P4.xml"
    return xmlmap.load_xmlobject_from_file(xml_path, Text)


def page_data(volume_id):
    tcp_text = load_tcp_text(volume_id)
    for page in tcp_text.pages:
        page_info = {
            "label": page.number,
            "content": str(page),
            "tags": [page.section_type],
        }
        yield page_info


def page_count(volume_id):
    xml_path = Path(settings.EEBO_DATA) / f"{short_id(volume_id)}.P4.xml"
    tcp_text = xmlmap.load_xmlobject_from_file(xml_path, Text)
    # provisional page count based on number of page beginning tags
    # NOTE: for simplicity, we include pages with no content
    return len(tcp_text.pages)
