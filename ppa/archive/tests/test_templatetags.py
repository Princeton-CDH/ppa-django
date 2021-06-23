from unittest.mock import Mock

from django.http import QueryDict
from django.utils.safestring import SafeString

from ppa.archive.templatetags.ppa_tags import (
    HATHI_BASE_URL,
    dict_item,
    gale_page_url,
    hathi_page_url,
    page_image_url,
    querystring_replace,
    solr_highlight,
)


def test_dict_item():
    # no error on not found
    assert dict_item({}, "foo") is None
    # string key
    assert dict_item({"foo": "bar"}, "foo") is "bar"
    # integer key
    assert dict_item({13: "lucky"}, 13) is "lucky"
    # integer value
    assert dict_item({13: 7}, 13) is 7


def test_querystring_replace():
    mockrequest = Mock()
    mockrequest.GET = QueryDict("query=saussure")
    context = {"request": mockrequest}
    # replace when arg is not present
    args = querystring_replace(context, page=1)
    # preserves existing args
    assert "query=saussure" in args
    # adds new arg
    assert "page=1" in args

    mockrequest.GET = QueryDict("query=saussure&page=2")
    args = querystring_replace(context, page=3)
    assert "query=saussure" in args
    # replaces existing arg
    assert "page=3" in args
    assert "page=2" not in args

    # handle repeating terms
    mockrequest.GET = QueryDict("language=english&language=french")
    args = querystring_replace(context, page=10)
    assert "language=english" in args
    assert "language=french" in args
    assert "page=10" in args


def test_page_image_url():
    # basic test with order, width, and item id
    item_id = "mdp.39015031594768"
    order = 29
    width = 300
    img_url = page_image_url(item_id, order, width)
    # points to the appropriate url
    assert img_url.startswith("%s/imgsrv/image?" % HATHI_BASE_URL)
    # renders the correct query string
    assert img_url.endswith("image?id=%s;seq=%s;width=%s" % (item_id, order, width))
    # test with width < 250; should use thumbnail API
    width = 250
    img_url = page_image_url(item_id, order, width)
    # points to the appropriate url
    assert img_url.startswith("%s/imgsrv/thumbnail?" % HATHI_BASE_URL)


def test_hathi_page_url():
    item_id = "mdp.39015031594768"
    order = 50
    hathi_url = hathi_page_url(item_id, order)
    assert hathi_url.startswith("%s/pt" % HATHI_BASE_URL)
    assert hathi_url.endswith("?id=%s;view=1up;seq=%s" % (item_id, order))


def test_gale_page_url():
    source_url = "https://link.gale.com/apps/doc/CW0123455/ECCO?u=abc123&sid=gale_api&xid=1605fa6c"
    order = 248
    gale_url = gale_page_url(source_url, order)
    assert gale_url == "%s&pg=248" % source_url


def test_solr_highlight():
    # simple text snippet
    val = """Make the cold air fire EaFeF
Sbelley, <em>Prometheus</em>, II. v.
6. """
    highlighted = solr_highlight(val)
    # should be marked as a safe string
    assert isinstance(highlighted, SafeString)
    # text should be equivalent, since nothing here needs escaping
    assert val == highlighted

    # value with ocr that looks like a bad tag
    val = """<s Shelley, <em>Prometheus</em>, II. v."""
    highlighted = solr_highlight(val)
    assert isinstance(highlighted, SafeString)
    # < should be escaped
    assert highlighted.startswith("&lt;s Shelley")
    # check that output is unchanged if autoescape is off
    highlighted = solr_highlight(val, autoescape=False)
    assert highlighted == val
