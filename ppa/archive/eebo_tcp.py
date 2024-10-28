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
    # count following notes as a quick check to bail out of note detection logic
    # (can't use eulxml boolean field here because it assumes string values for true/false)
    has_notes = xmlmap.IntegerField("count(following::NOTE)")

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
        if parent.tag == "NOTE" and text.is_text:
            within_note = parent
        # otherwise, check if text is nested somewhere under a note tag
        else:
            # get the first/nearest ancestor note, if there is one
            note_ancestors = parent.xpath("ancestor::NOTE[1]")
            within_note = note_ancestors[0] if note_ancestors else None

        return within_note

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
