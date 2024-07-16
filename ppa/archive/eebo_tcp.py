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

    def __repr__(self):
        return f"<Page {self.number or '-'} ({self.section_type})>"

    def page_contents(self):
        """generator of text strings between this page beginning tag and
        the next one"""

        # strictly speaking we are returning lxml "smart strings"
        # (lxml.etree._ElementUnicodeResult)

        # iterate and yield text following the current page
        # break until we hit the next page beginning
        for i, text in enumerate(self.text_contents):
            parent = text.getparent()

            # lxml handles text between elements as "tail" text;
            # the parent of the tail text is the preceding element
            if text.is_tail and parent.tag == "GAP":
                # if text precedes a GAP tag, include the display content
                # from the DISP attribute (for now)
                yield text.getparent().get("DISP")

            if text.is_tail and parent.tag == "PB":
                # the first loop is the first text node in the current page;
                # any iteration after that that comes after a PB
                # is the end of this page
                if i > 0:
                    break

            yield text

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
    pages = xmlmap.NodeListField("EEBO/TEXT//PB", Page)


def page_data(volume_id):
    xml_path = Path(settings.EEBO_DATA) / f"{short_id(volume_id)}.P4.xml"
    tcp_text = xmlmap.load_xmlobject_from_file(xml_path, Text)

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
