from unittest.mock import Mock

from django.http import QueryDict
from django.utils.safestring import SafeString

from ppa.archive.templatetags.ppa_tags import (
    HATHI_BASE_URL,
    coins_data,
    coins_encode,
    dict_item,
    first_page,
    gale_page_url,
    hathi_page_url,
    last_page,
    page_image_url,
    querystring_replace,
    solr_highlight,
)


def test_dict_item():
    # no error on not found
    assert dict_item({}, "foo") is None
    # string key
    assert dict_item({"foo": "bar"}, "foo") == "bar"
    # integer key
    assert dict_item({13: "lucky"}, 13) == "lucky"
    # integer value
    assert dict_item({13: 7}, 13) == 7


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
    assert hathi_url.endswith("?id=%s&view=1up&seq=%s" % (item_id, order))


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


def test_first_page():
    """Test the first_page template filter"""
    # Simple range
    assert first_page("10-15") == "10"
    # Single page
    assert first_page("42") == "42"
    # Empty/None
    assert first_page("") == ""
    assert first_page(None) == ""
    # Roman numerals
    assert first_page("xii-xvi") == "xii"


def test_last_page():
    """Test the last_page template filter"""
    # Simple range
    assert last_page("10-15") == "15"
    # Single page
    assert last_page("42") == "42"
    # Empty/None
    assert last_page("") == ""
    assert last_page(None) == ""
    # Roman numerals
    assert last_page("xii-xvi") == "xvi"
    # Complex range with commas
    assert last_page("10-15, 20-25") == "25"


def test_coins_data_full_work():
    """Test coins_data template tag for full works"""
    # Mock a DigitizedWork instance
    mock_work = Mock()
    mock_work._meta = True  # Mark as model instance
    mock_work.item_type = "F"  # Full work
    mock_work.FULL = "F"
    mock_work.EXCERPT = "E"
    mock_work.ARTICLE = "A"
    mock_work.title = "Test Book"
    mock_work.author = "Test Author"
    mock_work.pub_date = "1850"
    mock_work.publisher = "Test Publisher"
    mock_work.get_absolute_url.return_value = "/archive/detail/test123/"

    # Mock request context
    mock_request = Mock()
    mock_request.build_absolute_uri.return_value = (
        "http://testserver/archive/detail/test123/"
    )
    context = {"request": mock_request}

    result = coins_data(context, mock_work)

    assert result["ctx_ver"] == "Z39.88-2004"
    assert result["rft_val_fmt"] == "info:ofi/fmt:kev:mtx:book"
    assert result["rft.genre"] == "book"
    assert result["rft.title"] == "Test Book"
    assert result["rft.au"] == "Test Author"
    assert result["rft.date"] == "1850"
    assert result["rft.pub"] == "Test Publisher"
    assert result["rft_id"] == "http://testserver/archive/detail/test123/"


def test_coins_data_excerpt():
    """Test coins_data template tag for excerpts"""
    # Mock a DigitizedWork instance
    mock_work = Mock()
    mock_work._meta = True  # Mark as model instance
    mock_work.item_type = "E"  # Excerpt
    mock_work.FULL = "F"
    mock_work.EXCERPT = "E"
    mock_work.ARTICLE = "A"
    mock_work.title = "Test Excerpt"
    mock_work.author = "Test Author"
    mock_work.book_journal = "Test Book"
    mock_work.pages_orig = "10-15"
    mock_work.get_absolute_url.return_value = "/archive/detail/test123/"

    # Mock request context
    mock_request = Mock()
    mock_request.build_absolute_uri.return_value = (
        "http://testserver/archive/detail/test123/"
    )
    context = {"request": mock_request}

    result = coins_data(context, mock_work)

    assert result["rft_val_fmt"] == "info:ofi/fmt:kev:mtx:book"
    assert result["rft.genre"] == "bookitem"
    assert result["rft.atitle"] == "Test Excerpt"
    assert result["rft.btitle"] == "Test Book"
    assert result["rft.au"] == "Test Author"
    assert result["rft.pages"] == "10-15"
    assert result["rft.spage"] == "10"
    assert result["rft.epage"] == "15"


def test_coins_data_article():
    """Test coins_data template tag for articles"""
    # Mock a DigitizedWork instance
    mock_work = Mock()
    mock_work._meta = True  # Mark as model instance
    mock_work.item_type = "A"  # Article
    mock_work.FULL = "F"
    mock_work.EXCERPT = "E"
    mock_work.ARTICLE = "A"
    mock_work.title = "Test Article"
    mock_work.author = "Test Author"
    mock_work.book_journal = "Test Journal"
    mock_work.enumcron = "Vol. 5"
    mock_work.pages_orig = "25-30"
    mock_work.get_absolute_url.return_value = "/archive/detail/test123/"

    # Mock request context
    mock_request = Mock()
    mock_request.build_absolute_uri.return_value = (
        "http://testserver/archive/detail/test123/"
    )
    context = {"request": mock_request}

    result = coins_data(context, mock_work)

    assert result["rft_val_fmt"] == "info:ofi/fmt:kev:mtx:journal"
    assert result["rft.genre"] == "article"
    assert result["rft.atitle"] == "Test Article"
    assert result["rft.jtitle"] == "Test Journal"
    assert result["rft.au"] == "Test Author"
    assert result["rft.volume"] == "Vol. 5"
    assert result["rft.pages"] == "25-30"
    assert result["rft.spage"] == "25"
    assert result["rft.epage"] == "30"


def test_coins_data_solr_result():
    """Test coins_data template tag for Solr search results"""
    from unittest.mock import patch

    # Mock a Solr result (no _meta attribute)
    mock_item = Mock()
    del mock_item._meta  # Ensure no _meta attribute
    mock_item.work_type = "full-work"
    mock_item.title = "Test Solr Book"
    mock_item.author = "Solr Author"
    mock_item.source_id = "test456"
    mock_item.first_page = None

    # Mock request context
    mock_request = Mock()
    mock_request.build_absolute_uri.return_value = (
        "http://testserver/archive/detail/test456/"
    )
    context = {"request": mock_request}

    with patch("django.urls.reverse") as mock_reverse:
        mock_reverse.return_value = "/archive/detail/test456/"
        result = coins_data(context, mock_item)

    assert result["rft_val_fmt"] == "info:ofi/fmt:kev:mtx:book"
    assert result["rft.genre"] == "book"
    assert result["rft.title"] == "Test Solr Book"
    assert result["rft.au"] == "Solr Author"


def test_coins_encode():
    """Test coins_encode template filter"""
    test_data = {
        "ctx_ver": "Z39.88-2004",
        "rft_val_fmt": "info:ofi/fmt:kev:mtx:book",
        "rft.genre": "book",
        "rft.title": "Test & Title",
        "au": "Test Author",
        "rft_id": "http://example.com/test?param=value",
    }

    result = coins_encode(test_data)

    # Should return a span element
    assert '<span class="Z3988"' in str(result)
    assert "title=" in str(result)
    # Should URL encode values
    assert "Test+%26+Title" in str(result)  # URL encoded title (+ for spaces)
    assert "http%3A%2F%2Fexample.com%2Ftest%3Fparam%3Dvalue" in str(
        result
    )  # URL encoded URL
    # Should use &amp; between parameters
    assert "&amp;" in str(result)

    # Test with empty data
    assert coins_encode({}) == ""
    assert coins_encode(None) == ""
