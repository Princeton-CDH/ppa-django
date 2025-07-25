from unittest.mock import Mock, patch

from django.http import QueryDict
from django.utils.safestring import SafeString

from ppa.archive.templatetags.ppa_tags import (
    HATHI_BASE_URL,
    coins_data,
    coins_encode,
    dict_item,
    gale_page_url,
    hathi_page_url,
    page_image_url,
    querystring_replace,
    solr_highlight,
)


def test_dict_item():
    # Test graceful handling of missing keys
    assert dict_item({}, "foo") is None
    # Test string key access
    assert dict_item({"foo": "bar"}, "foo") == "bar"
    # Test integer key access
    assert dict_item({13: "lucky"}, 13) == "lucky"
    # Test integer value retrieval
    assert dict_item({13: 7}, 13) == 7


def test_querystring_replace():
    mockrequest = Mock()
    mockrequest.GET = QueryDict("query=saussure")
    context = {"request": mockrequest}

    # Test adding new parameter while preserving existing ones
    args = querystring_replace(context, page=1)
    assert "query=saussure" in args  # Preserves existing search query
    assert "page=1" in args  # Adds new pagination parameter

    # Test replacing existing parameter value
    mockrequest.GET = QueryDict("query=saussure&page=2")
    args = querystring_replace(context, page=3)
    assert "query=saussure" in args  # Still preserves other parameters
    assert "page=3" in args  # Updates the page parameter
    assert "page=2" not in args  # Removes old page value

    # Test handling multiple values for same parameter
    mockrequest.GET = QueryDict("language=english&language=french")
    args = querystring_replace(context, page=10)
    assert "language=english" in args  # Preserves first language value
    assert "language=french" in args  # Preserves second language value
    assert "page=10" in args  # Adds new parameter


def test_page_image_url():
    item_id = "mdp.39015031594768"
    order = 29
    width = 300

    # Test full image API for larger widths (>250px)
    img_url = page_image_url(item_id, order, width)
    assert img_url.startswith("%s/imgsrv/image?" % HATHI_BASE_URL)
    assert img_url.endswith("image?id=%s;seq=%s;width=%s" % (item_id, order, width))

    # Test thumbnail API for smaller widths (≤250px)
    width = 250
    img_url = page_image_url(item_id, order, width)
    assert img_url.startswith("%s/imgsrv/thumbnail?" % HATHI_BASE_URL)


def test_hathi_page_url():
    item_id = "mdp.39015031594768"
    order = 50
    hathi_url = hathi_page_url(item_id, order)
    # Verify URL points to HathiTrust page turner
    assert hathi_url.startswith("%s/pt" % HATHI_BASE_URL)
    # Verify URL includes correct item ID and page sequence
    assert hathi_url.endswith("?id=%s&view=1up&seq=%s" % (item_id, order))


def test_gale_page_url():
    source_url = "https://link.gale.com/apps/doc/CW0123455/ECCO?u=abc123&sid=gale_api&xid=1605fa6c"
    order = 248
    gale_url = gale_page_url(source_url, order)
    # Verify page parameter is appended to existing URL
    assert gale_url == "%s&pg=248" % source_url


def test_solr_highlight():
    # Test basic highlighting with clean content
    val = """Make the cold air fire EaFeF
Sbelley, <em>Prometheus</em>, II. v.
6. """
    highlighted = solr_highlight(val)
    assert isinstance(highlighted, SafeString)  # Returns safe HTML
    assert val == highlighted  # No escaping needed for clean content

    # Test HTML escaping with potentially dangerous content
    val = """<s Shelley, <em>Prometheus</em>, II. v."""
    highlighted = solr_highlight(val)
    assert isinstance(highlighted, SafeString)
    assert highlighted.startswith("&lt;s Shelley")  # Escapes < to &lt;

    # Test autoescape toggle functionality
    highlighted = solr_highlight(val, autoescape=False)
    assert highlighted == val  # No escaping when autoescape=False


def test_coins_data_full_work():
    """Test coins_data template tag for generating COinS metadata for full works."""
    # Mock a complete book record from Solr
    mock_work = Mock()
    mock_work.work_type = "full-work"
    mock_work.title = "Test Book"
    mock_work.author = "Test Author"
    mock_work.pub_date = "1850"
    mock_work.publisher = "Test Publisher"
    mock_work.pub_place = "Cambridge"
    mock_work.source_id = "test123"
    mock_work.first_page = None

    # Mock Django request context for URL generation
    mock_request = Mock()
    mock_request.build_absolute_uri.return_value = (
        "http://testserver/archive/detail/test123/"
    )
    context = {"request": mock_request}

    with patch("django.urls.reverse") as mock_reverse:
        mock_reverse.return_value = "/archive/detail/test123/"
        result = coins_data(context, mock_work)

    # Verify COinS standard compliance
    assert result["ctx_ver"] == "Z39.88-2004"  # COinS version
    assert result["rft_val_fmt"] == "info:ofi/fmt:kev:mtx:book"  # Book format
    assert result["genre"] == "book"  # Full work type

    # Verify bibliographic metadata mapping
    assert result["title"] == "Test Book"
    assert result["au"] == "Test Author"
    assert result["date"] == "1850"
    assert result["pub"] == "Test Publisher"
    assert result["place"] == "Cambridge"
    assert result["rft_id"] == "http://testserver/archive/detail/test123/"


def test_coins_data_excerpt():
    """Test coins_data template tag for generating COinS metadata for book excerpts.
    Excerpts require different COinS formatting than full works, using 'bookitem'
    genre and mapping titles to 'atitle' (article title) with 'btitle' (book title)
    for the containing work.
    """
    # Mock a book excerpt record from Solr
    mock_work = Mock()
    mock_work.work_type = "excerpt"
    mock_work.title = "Test Excerpt"
    mock_work.author = "Test Author"
    mock_work.book_journal = "Test Book"
    mock_work.pub_place = "Oxford"
    mock_work.first_page = "10"
    mock_work.last_page = "15"
    mock_work.source_id = "test123"

    mock_request = Mock()
    mock_request.build_absolute_uri.return_value = (
        "http://testserver/archive/detail/test123/"
    )
    context = {"request": mock_request}

    with patch("django.urls.reverse") as mock_reverse:
        mock_reverse.return_value = "/archive/detail/test123/"
        result = coins_data(context, mock_work)

    # Verify excerpt-specific COinS formatting
    assert result["rft_val_fmt"] == "info:ofi/fmt:kev:mtx:book"
    assert result["genre"] == "bookitem"  # Excerpt type

    # Verify title mapping for excerpts
    assert result["atitle"] == "Test Excerpt"  # Article/excerpt title
    assert result["btitle"] == "Test Book"  # Containing book title

    # Verify page range information
    assert result["au"] == "Test Author"
    assert result["place"] == "Oxford"
    assert result["pages"] == "10-15"  # Full page range
    assert result["spage"] == "10"  # Start page
    assert result["epage"] == "15"  # End page


def test_coins_data_article():
    """Test coins_data template tag for generating COinS metadata for journal articles.
    Articles use the journal metadata format with 'jtitle' for journal name
    and 'volume' for issue information, distinct from book excerpts.
    """
    # Mock a journal article record from Solr
    mock_work = Mock()
    mock_work.work_type = "article"
    mock_work.title = "Test Article"
    mock_work.author = "Test Author"
    mock_work.book_journal = "Test Journal"
    mock_work.enumcron = "Vol. 5"
    mock_work.first_page = "25"
    mock_work.last_page = "30"
    mock_work.source_id = "test123"

    mock_request = Mock()
    mock_request.build_absolute_uri.return_value = (
        "http://testserver/archive/detail/test123/"
    )
    context = {"request": mock_request}

    with patch("django.urls.reverse") as mock_reverse:
        mock_reverse.return_value = "/archive/detail/test123/"
        result = coins_data(context, mock_work)

    # Verify journal article COinS formatting
    assert result["rft_val_fmt"] == "info:ofi/fmt:kev:mtx:journal"  # Journal format
    assert result["genre"] == "article"  # Article type

    # Verify journal-specific metadata mapping
    assert result["atitle"] == "Test Article"  # Article title
    assert result["jtitle"] == "Test Journal"  # Journal title
    assert result["au"] == "Test Author"
    assert result["volume"] == "Vol. 5"  # Volume/issue info

    # Verify page range for articles
    assert result["pages"] == "25-30"
    assert result["spage"] == "25"
    assert result["epage"] == "30"


def test_coins_data_solr_object_excerpt():
    """Test coins_data with properly working AliasedSolrQuerySet objects.
    This tests the ideal scenario where Solr field aliasing is working correctly
    and all fields are accessible via clean attribute names rather than
    raw Solr field names like 'work_type_s'.
    """
    # Mock Solr object with clean aliased field names
    mock_item = Mock()
    mock_item.work_type = "excerpt"
    mock_item.title = "Test Excerpt"
    mock_item.author = "Test Author"
    mock_item.book_journal = "Test Book"
    mock_item.pub_place = "Oxford"
    mock_item.first_page = "10"
    mock_item.last_page = "15"
    mock_item.source_id = "test123"

    mock_request = Mock()
    mock_request.build_absolute_uri.return_value = (
        "http://testserver/archive/detail/test123/"
    )
    context = {"request": mock_request}

    with patch("django.urls.reverse") as mock_reverse:
        mock_reverse.return_value = "/archive/detail/test123/"
        result = coins_data(context, mock_item)

    # Verify basic excerpt functionality with Solr objects
    assert result["rft_val_fmt"] == "info:ofi/fmt:kev:mtx:book"
    assert result["genre"] == "bookitem"
    assert result["atitle"] == "Test Excerpt"
    assert result["btitle"] == "Test Book"


def test_coins_data_dictionary():
    """Test coins_data with plain dictionary objects.
    This tests the scenario where data comes as a plain Python dictionary
    rather than a Solr object, ensuring the function handles both data
    structures correctly.
    """
    # Plain dictionary with clean field names
    mock_item = {
        "work_type": "article",
        "title": "Test Article",
        "author": "Test Author",
        "book_journal": "Test Journal",
        "enumcron": "Vol. 5",
        "first_page": "25",
        "last_page": "30",
        "source_id": "test123",
    }

    mock_request = Mock()
    mock_request.build_absolute_uri.return_value = (
        "http://testserver/archive/detail/test123/"
    )
    context = {"request": mock_request}

    with patch("django.urls.reverse") as mock_reverse:
        mock_reverse.return_value = "/archive/detail/test123/"
        result = coins_data(context, mock_item)

    # Verify dictionary input produces correct article metadata
    assert result["rft_val_fmt"] == "info:ofi/fmt:kev:mtx:journal"
    assert result["genre"] == "article"
    assert result["atitle"] == "Test Article"
    assert result["jtitle"] == "Test Journal"


def test_coins_encode():
    """Test coins_encode template filter for converting COinS metadata to HTML."""
    test_data = {
        "ctx_ver": "Z39.88-2004",
        "rft_val_fmt": "info:ofi/fmt:kev:mtx:book",
        "rft.genre": "book",
        "rft.title": "Test & Title",  # Contains special character
        "rft.au": "Test Author",
        "rft_id": "http://example.com/test?param=value",  # Contains URL characters
    }

    result = coins_encode(test_data)

    # Verify HTML structure for COinS detection
    assert '<span class="Z3988"' in str(result)  # Standard COinS class
    assert "title=" in str(result)  # Metadata in title attribute

    # Verify URL encoding of special characters
    assert "Test+%26+Title" in str(result)  # & encoded as %26, space as +
    assert "http%3A%2F%2Fexample.com%2Ftest%3Fparam%3Dvalue" in str(
        result
    )  # URL encoded

    # Verify HTML entity encoding for parameter separation
    assert "&amp;" in str(result)  # & encoded as &amp; for HTML

    # Test edge cases
    assert coins_encode({}) == ""  # Empty dictionary
    assert coins_encode(None) == ""  # None input


def test_coins_data_raw_solr_fields():
    """Test coins_data with raw Solr field names (with _s suffixes).
    This tests the scenario where Solr aliasing isn't working properly
    and we get the raw field names instead of clean aliases.
    """
    # Mock Solr object with raw field names as they actually exist in Solr
    mock_item = Mock()
    mock_item.work_type_s = "excerpt"  # Raw Solr field name
    mock_item.title = "Test Excerpt"
    mock_item.author = "Test Author"
    mock_item.book_journal_s = "Test Book"  # Raw Solr field name
    mock_item.pub_place = "Oxford"
    mock_item.first_page_s = "10"  # Raw Solr field name
    mock_item.last_page_s = "15"  # Raw Solr field name
    mock_item.source_id = "test123"

    # Make clean field names return None (simulating broken aliasing)
    mock_item.work_type = None
    mock_item.book_journal = None
    mock_item.first_page = None
    mock_item.last_page = None

    mock_request = Mock()
    mock_request.build_absolute_uri.return_value = (
        "http://testserver/archive/detail/test123/"
    )
    context = {"request": mock_request}

    with patch("django.urls.reverse") as mock_reverse:
        mock_reverse.return_value = "/archive/detail/test123/"
        result = coins_data(context, mock_item)

    # If the code only looks for clean field names, this should fail
    # because work_type would be None, defaulting to "full-work"
    # But we want it to find work_type_s and use "excerpt"
    assert result["genre"] == "bookitem"  # Should be excerpt behavior
    assert result["atitle"] == "Test Excerpt"


def test_coins_data_mixed_field_names():
    """Test coins_data with a mix of clean and raw field names.
    This simulates partial aliasing where some fields are aliased and others aren't.
    """
    mock_item = Mock()
    # Some fields have clean names (aliasing working)
    mock_item.work_type = "article"
    mock_item.title = "Test Article"
    mock_item.author = "Test Author"

    # Some fields only have raw names (aliasing broken for these)
    mock_item.book_journal_s = "Test Journal"  # Only raw name available
    mock_item.book_journal = None  # Clean name not available
    mock_item.enumcron = "Vol. 5"
    mock_item.first_page_s = "25"  # Only raw name
    mock_item.first_page = None  # Clean name not available
    mock_item.last_page_s = "30"
    mock_item.last_page = None
    mock_item.source_id = "test123"

    mock_request = Mock()
    mock_request.build_absolute_uri.return_value = (
        "http://testserver/archive/detail/test123/"
    )
    context = {"request": mock_request}

    with patch("django.urls.reverse") as mock_reverse:
        mock_reverse.return_value = "/archive/detail/test123/"
        result = coins_data(context, mock_item)

    assert result["rft_val_fmt"] == "info:ofi/fmt:kev:mtx:journal"
    assert result["genre"] == "article"
    assert result["atitle"] == "Test Article"


def test_coins_data_django_model():
    """Test coins_data with Django model objects.
    This tests the functionality where the tag can work directly with
    DigitizedWork model instances using properties.
    """
    # Mock Django model object with properties
    mock_model = Mock()
    mock_model.work_type = "excerpt"  # Property we added
    mock_model.title = "Django Model Test"
    mock_model.author = "Model Author"
    mock_model.book_journal = "Test Book Journal"
    mock_model.pub_place = "Model City"
    mock_model.source_id = "django123"

    # Mock properties
    mock_model.first_page = "5"
    mock_model.last_page = "10"

    mock_request = Mock()
    mock_request.build_absolute_uri.return_value = (
        "http://testserver/archive/detail/django123/"
    )
    context = {"request": mock_request}

    with patch("django.urls.reverse") as mock_reverse:
        mock_reverse.return_value = "/archive/detail/django123/"
        result = coins_data(context, mock_model)

    # Verify Django model functionality
    assert result["rft_val_fmt"] == "info:ofi/fmt:kev:mtx:book"
    assert result["genre"] == "bookitem"  # Excerpt type
    assert result["atitle"] == "Django Model Test"  # Article/excerpt title
    assert result["btitle"] == "Test Book Journal"  # Containing book title
    assert result["au"] == "Model Author"
    assert result["place"] == "Model City"
    assert result["spage"] == "5"  # From first_page property
    assert result["epage"] == "10"  # From last_page property
    assert result["pages"] == "5-10"  # Constructed range
