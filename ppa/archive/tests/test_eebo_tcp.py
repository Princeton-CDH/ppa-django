import os.path

from eulxml.xmlmap import load_xmlobject_from_file

from ppa.archive import eebo_tcp
from ppa.archive.tests.test_models import FIXTURES_PATH

TCP_FIXTURE = os.path.join(FIXTURES_PATH, "A25820.P4.xml")


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
