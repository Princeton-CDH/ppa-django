"""
Code for working with EEBO-TCP (Text Creation Partnership) content.
"""
from pathlib import Path

from django.conf import settings
from eulxml import xmlmap


def short_id(volume_id):
    # volume ids in import spreadsheet are in this format: A25820.0001.001
    # TCP records use the first portion only
    return volume_id.split(".")[0]


class Page(xmlmap.XmlObject):
    """A page of content in an EEBO-TCP text"""

    #: reference id for image scan (two pages per image)
    ref = xmlmap.StringField("@REF")
    #: source page number (optional)
    number = xmlmap.StringField("@N")

    # parent div type =~ page type / label ?
    section_type = xmlmap.StringField("ancestor::DIV1/@TYPE")

    # page beginning tags delimit content instead of containing it;
    # use following axis to find all text nodes following this page beginning
    text_contents = xmlmap.StringListField("following::text()")

    # notes on or after this page, for managing footnote text
    notes = xmlmap.NodeListField("following::NOTE", xmlmap.XmlObject)

    def __repr__(self):
        return f"<Page {self.number or '-'} ({self.section_type})>"

    # footnote indicators
    note_marks = ["*", "†", "‡", "§"]
    num_note_marks = len(note_marks)

    def get_note_mark(self, i):
        """Generate a note marker based on note index and :attr:`note_marks`;
        symbols are used in order and then doubled, tripled, etc as needed."""

        # use modulo to map to the list of available marks
        mark_index = i % self.num_note_marks
        # use division to determine how many times to repeat the mark
        repeat = int(i / self.num_note_marks) + 1
        return self.note_marks[mark_index] * repeat

    def text_inside_note(self, text):
        """check if a text element occurs within a NOTE element; if so,
        return the note element"""

        # bail out if there are no notes following this page
        if not self.notes:
            return None

        within_note = None
        # check if this text is directly inside a note tag
        parent = text.getparent()
        if parent.tag == "NOTE" and not text.is_tail:
            within_note = parent
        # otherwise, check if text is nested under a note tag
        else:
            for ancestor in parent.iterancestors():
                if ancestor.tag == "NOTE":
                    within_note = ancestor
                    break

        return within_note

    def note_index(self, note):
        # given a note element, determine the 0-based index on this page

        # use a for loop so we can bail out once we get a match
        for i, n in enumerate(self.notes):
            if n.node == note:
                return i

        # in normal use the note should be found; raise an exception
        # if it is not so this will fail loudly
        raise ValueError

    def page_contents(self):
        """generator of text strings between this page beginning tag and
        the next one"""

        # strictly speaking we are returning lxml "smart strings"
        # (lxml.etree._ElementUnicodeResult)

        # collect any notes and include after main page text contents
        notes = []

        # iterate and yield text following the current page
        # break until we hit the next page beginning
        for i, text in enumerate(self.text_contents):
            parent = text.getparent()

            # determine if this text falls inside a note tag
            within_note = self.text_inside_note(text)
            if within_note is not None:
                # and if so, which one
                note_index = self.note_index(within_note)
                # if this is the first text for this note,
                # add a marker inline with the text AND the note
                # index equals length, start a new note at the end of the list of notes
                if len(notes) == note_index:
                    # some note tags have an N attribute; use if present
                    # otherwise, use a note mark from our list of symbols
                    note_mark = within_note.get("N", self.get_note_mark(note_index))
                    yield note_mark
                    notes.append(f"\n{note_mark} ")

                # add text to the appropriate note
                notes[note_index] = f"{notes[note_index]}{text}"

                # skip to next loop
                continue

            # lxml handles text between elements as "tail" text;
            # the parent of the tail text is the preceding element
            if text.is_tail and parent.tag == "GAP":
                # if text precedes a GAP tag, include the display content
                # from the DISP ` (for now)
                yield text.getparent().get("DISP")

            if text.is_tail and parent.tag == "PB":
                # the first loop is the first text node in the current page;
                # any iteration after that that comes after a PB
                # is the end of this page
                if i > 0:
                    break

            yield text

        # if this page includes notes, yield notes after main text content
        if notes:
            # yield two blank lines to separate main text content from notes
            yield "\n\n"
            yield from notes

    divider = "∣"

    def __str__(self):
        # NOTE: P4 EEBO-TCP content uses unicode divider character ∣
        # to indicate page breaks that caused hyphenated words
        # in the original text; remove them
        return "".join(self.page_contents()).replace(self.divider, "")


class Text(xmlmap.XmlObject):
    """:class:~`eulxml.xmlmap.XmlObject` for extracting page text from
    EEBO-TCP P4 xml"""

    # EEBO-TCP TEI does not use or declare any namespaces

    # pages are delimited by page beginning tags, which may occur at
    # various levels nested within divs, paragraphs, etc

    #: list of page objects, identified by page beginning tag (PB)
    pages = xmlmap.NodeListField("EEBO//TEXT//PB", Page)


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
