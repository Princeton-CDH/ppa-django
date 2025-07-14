import re

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from urllib.parse import urlencode

register = template.Library()


@register.filter
def dict_item(dictionary, key):
    """'Template filter to allow accessing dictionary value by variable key.
    Example use::

        {{ mydict|dict_item:keyvar }}
    """
    return dictionary.get(key, None)


@register.simple_tag(takes_context=True)
def querystring_replace(context, **kwargs):
    """Template tag to simplify retaining querystring parameters
    when paging through search results with active filters.
    Example use::

        <a href="?{% querystring_replace page=paginator.next_page_number %}">
    """
    # borrowed as-is from derrida codebase
    # inspired by https://stackoverflow.com/questions/2047622/how-to-paginate-django-with-other-get-variables

    # get a mutable copy of the current request
    querystring = context["request"].GET.copy()
    # update with any parameters passed in
    # NOTE: needs to *set* fields rather than using update,
    # because QueryDict update appends to field rather than replacing
    for key, val in kwargs.items():
        querystring[key] = val
    # return urlencoded query string
    return mark_safe(querystring.urlencode())  # don't encode & as &amp;


# NOTE: Use urllib.parse? Not sure it gets us much given the semi-colon
# delimited query strings.
#: Base url for HathiTrust assets
HATHI_BASE_URL = "https://babel.hathitrust.org/cgi"


@register.simple_tag
def page_image_url(item_id, order, width):
    """Generate a page image url based on an item id, page sequence label,
    and desired width. Currently HathiTrust specific. Uses Hathi's
    thumbnail API by default, switching to the image API for widths greater than
    250px.
    Example use::

        {% page_image_url item_id page.order 220 %}
    """
    service = "image" if width > 250 else "thumbnail"
    return "%s/imgsrv/%s?id=%s;seq=%s;width=%s" % (
        HATHI_BASE_URL,
        service,
        item_id,
        order,
        width,
    )


@register.simple_tag
def hathi_page_url(item_id, order):
    """Generate a link to HathiTrust for an individual page
    Example use::

        {% page_url item_id page.order %}
    """
    return mark_safe(
        "{}/pt?id={}&view=1up&seq={}".format(HATHI_BASE_URL, item_id, order)
    )


@register.simple_tag
def gale_page_url(item_url, order):
    # add page number to existing source url (i.e., isShownAt URL from API);
    # (assumes that url already has some query parameters, as they currently always do)
    return "{}&pg={}".format(item_url, order)


#: regular expression to identify open and close <em> tags in solr
#: highlighting snippets
EM_TAG_RE = re.compile(r"(</?em>)")


@register.filter(needs_autoescape=True)
@stringfilter
def solr_highlight(value, autoescape=True):
    """Filter to render solr highlighting snippets for display.  Marks
    open and close <em> tags as safe and escapes all other text."""

    # use conditional escape per django documentation
    # https://docs.djangoproject.com/en/1.11/howto/custom-template-tags/#filters-and-auto-escaping
    if autoescape:
        esc = conditional_escape
    else:

        def esc(x):
            return x

    # split the text on em tags; mark em tags as safe and
    # escape everything else
    return mark_safe(
        "".join(
            [
                mark_safe(part) if EM_TAG_RE.match(part) else esc(part)
                for part in EM_TAG_RE.split(value)
            ]
        )
    )


@register.filter
def first_page(page_range):
    """Extract first page number from a page range like '25-30' or '25'"""
    if not page_range:
        return ""
    return page_range.split("-")[0].strip()


@register.filter
def last_page(page_range):
    """Extract the last page number from a page range string.

    Examples:
        'xii-xvi' => 'xvi'
        '100-105' => '105'
        '42' => '42'
    """
    if not page_range:
        return ""

    # Use regex to find the last page number in various formats
    # Handles ranges like '12-15', 'xii-xvi', or single pages like '42'
    match = re.search(
        r"([a-z\d]+)(?:\s*[,-]\s*([a-z\d]+))*$", str(page_range), re.IGNORECASE
    )
    if match:
        # If there are multiple groups, return the last non-None group
        # This handles both ranges (returns second group) and single pages (returns first group)
        groups = match.groups()
        return groups[-1] if groups[-1] is not None else groups[0]
    return str(page_range)


@register.simple_tag(takes_context=True)
def coins_data(context, item):
    """Generate COinS metadata dictionary for Zotero.

    Handles both DigitizedWork model instances and Solr search results,
    adapting field access and work type detection accordingly.

    Args:
        context: Django template context (for request)
        item: DigitizedWork instance or Solr search result dict

    Returns:
        dict: COinS metadata fields ready for encoding
    """
    # Determine if this is a model instance or Solr result
    is_model_instance = hasattr(item, "_meta")

    # Helper function to get attribute/key from either object or dict:
    # Search results come from Solr as dictionaries: item['title']
    # Detail pages use Django models as objects: item.title
    def get_item_value(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        else:
            return getattr(obj, key, default)

    # Get work type:
    # Model instances have constants (item.FULL='F')
    # Solr has strings ('full-work')
    if is_model_instance:
        work_type = item.item_type
        # Map model constants to our internal strings for consistency
        type_map = {
            item.FULL: "full-work",
            item.EXCERPT: "excerpt",
            item.ARTICLE: "article",
        }
        work_type_str = type_map.get(work_type, "full-work")
    else:
        # Solr results store work_type as string
        work_type_str = get_item_value(item, "work_type", "full-work")

    # Generate absolute URL:
    # model instances have get_absolute_url method
    # Solr results need URL building
    if is_model_instance:
        absolute_url = context["request"].build_absolute_uri(item.get_absolute_url())
    else:
        source_id = get_item_value(item, "source_id")
        first_page = get_item_value(item, "first_page")

        if first_page:
            from django.urls import reverse

            detail_url = reverse(
                "archive:detail",
                kwargs={"source_id": source_id, "start_page": first_page},
            )
        else:
            from django.urls import reverse

            detail_url = reverse("archive:detail", kwargs={"source_id": source_id})
        absolute_url = context["request"].build_absolute_uri(detail_url)

    # Build base metadata dictionary
    data = {
        "ctx_ver": "Z39.88-2004",
        "rft_id": absolute_url,
    }

    # Add fields common to all types
    if get_item_value(item, "title"):
        data["title"] = get_item_value(item, "title")
    if get_item_value(item, "author"):
        data["au"] = get_item_value(item, "author")
    if get_item_value(item, "pub_date"):
        data["date"] = get_item_value(item, "pub_date")
    if get_item_value(item, "publisher"):
        data["pub"] = get_item_value(item, "publisher")

    # Type-specific metadata and format
    if work_type_str == "full-work":
        data.update({"rft_val_fmt": "info:ofi/fmt:kev:mtx:book", "rft.genre": "book"})
        # For books, title goes in rft.title
        if "title" in data:
            data["rft.title"] = data.pop("title")

    elif work_type_str == "excerpt":
        data.update(
            {"rft_val_fmt": "info:ofi/fmt:kev:mtx:book", "rft.genre": "bookitem"}
        )
        # For excerpts, `title` is article title, `book_journal` is book title
        if "title" in data:
            data["rft.atitle"] = data.pop("title")
        if get_item_value(item, "book_journal"):
            data["rft.btitle"] = get_item_value(item, "book_journal")
        # Add page information for excerpts (only available for model instances)
        if is_model_instance and get_item_value(item, "pages_orig"):
            pages_orig = get_item_value(item, "pages_orig")
            data["rft.pages"] = pages_orig
            data["rft.spage"] = first_page(pages_orig)
            data["rft.epage"] = last_page(pages_orig)

    elif work_type_str == "article":
        data.update(
            {"rft_val_fmt": "info:ofi/fmt:kev:mtx:journal", "rft.genre": "article"}
        )
        # For articles, title is article title, book_journal is journal title
        if "title" in data:
            data["rft.atitle"] = data.pop("title")
        if get_item_value(item, "book_journal"):
            data["rft.jtitle"] = get_item_value(item, "book_journal")
        # Add volume and page information for articles
        # only available for model instances; Solr results do not have this information
        if is_model_instance:
            if get_item_value(item, "enumcron"):
                data["rft.volume"] = get_item_value(item, "enumcron")
            if get_item_value(item, "pages_orig"):
                pages_orig = get_item_value(item, "pages_orig")
                data["rft.pages"] = pages_orig
                data["rft.spage"] = first_page(pages_orig)
                data["rft.epage"] = last_page(pages_orig)

    # Convert common fields to proper COinS format with rft. prefix
    if "au" in data:
        data["rft.au"] = data.pop("au")
    if "date" in data:
        data["rft.date"] = data.pop("date")
    if "pub" in data:
        data["rft.pub"] = data.pop("pub")

    return data


@register.filter
def coins_encode(coins_data):
    """Convert COinS metadata dictionary to encoded span element.

    Takes a dictionary of COinS fields and converts it to a properly
    encoded HTML span element for Zotero detection.

    Args:
        coins_data (dict): COinS metadata dictionary from coins_data tag

    Returns:
        SafeString: HTML span element with encoded COinS metadata
    """
    if not coins_data:
        return ""

    # Build the title attribute with properly encoded key=value pairs
    title_parts = []
    for key, value in coins_data.items():
        if value:  # Only include non-empty values
            # URL encode the value and ensure it's a string
            encoded_value = urlencode({"": str(value)})[1:]  # Remove leading '='
            title_parts.append(f"{key}={encoded_value}")

    # Ensure all parts are strings before joining
    title_attr = "&amp;".join(str(part) for part in title_parts)

    # Return the complete span element
    # Using mark_safe because we control the content and have properly escaped user data
    return mark_safe(f'<span class="Z3988" title="{title_attr}"></span>')
