"""
Code for working with EEBO-TCP (Text Creation Partnership) content.
"""

from eulxml import xmlmap


class Page(xmlmap.XmlObject):
    """A page of content in an EEBO-TCP text"""

    # not sure how these are used; repeat in pairs? page label (?)
    ref = xmlmap.StringField("@REF")
    #: page number (optional)
    number = xmlmap.StringField("@N")

    # parent div type =~ page type / label ?
    section_type = xmlmap.StringField("ancestor::DIV1/@TYPE")

    # page breaks delimit content instead of containing it;
    # use following axis to find all text nodes following this page break
    text_contents = xmlmap.StringListField("following::text()")

    def __repr__(self):
        return f"<Page {self.label} ({self.section_type})>"

    def page_contents(self):
        "generator of text strings between this page break and the next one"

        # strictly speaking we are returning lxml "smart strings"
        # (lxml.etree._ElementUnicodeResult)

        # iterate and yield text following the current page
        # break until we hit the next page break
        for i, text in enumerate(self.text_contents):
            # lxml handles text between elements as "tail" text;
            # the parent of the tail text is the preceding element
            if text.is_tail:
                # if text precedes a GAP tag, include the display content
                # from the DISP attribute (for now)
                if text.getparent().tag == "GAP":
                    yield text.getparent().get("DISP")

                # stop when hit the tail text that comes after the second
                # page break tag (not the first tail text after current PB)
                # or when we hit the end of a section (DIV1)
                if i > 0 and text.getparent().tag in ["PB", "DIV1"]:
                    break

            yield text

    def __str__(self):
        # TODO: should we do anything with divider character ∣ ?
        # does this indicate page breaks in the original?
        # (it can occur in the middle of words; do we check and introduce hyphens? remove?)
        return "".join(self.page_contents())


class Text(xmlmap.XmlObject):
    """:class:~`eulxml.xmlmap.XmlObject` for extracting page text from
    EEBO-TCP P4 xml"""

    # EEBO-TCP TEI does not use or declare any namespaces

    # pages are delimited by page breaks, which may occur at
    # various levels nested within divs, paragraphs, etc

    #: list of page objects, identified by starting page break tag (PB)
    pages = xmlmap.NodeListField("EEBO/TEXT//PB", Page)
