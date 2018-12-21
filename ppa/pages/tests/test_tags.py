from django.utils.timezone import now

from ppa.pages.templatetags.ppa_page_tags import format_citation


def test_format_citation():
    # fields replaced when present
    citation = 'PPA, version [SW_VERSION]. Accessed [DATE].'
    fmt_citation = format_citation(citation, '3.0')
    assert 'version 3.0.' in fmt_citation
    assert 'Accessed %s' % now().strftime('%d %B %Y') in fmt_citation

    # nothing changed if not present
    text = 'some other paragraph text with <i>formatting</i> etc'
    assert format_citation(text, '3.0') == text



