import re

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.html import conditional_escape, format_html
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


def _get_item_value(obj, key, default=None):
    """Get value from Solr object or dictionary.
    For Solr objects, tries clean field name first, then falls back to
    raw Solr field name with _s suffix if aliasing isn't working.
    """
    if isinstance(obj, dict):
        return obj.get(key, default)
    else:
        # Try clean field name first (from aliasing)
        value = getattr(obj, key, None)
        if value is not None:
            return value

        # Fall back to raw Solr field name with _s suffix
        raw_field_name = f"{key}_s"
        return getattr(obj, raw_field_name, default)


def _generate_absolute_url(context, item):
    """Generate absolute URL for the item from Solr result."""
    from django.urls import reverse

    source_id = _get_item_value(item, "source_id")
    first_page = _get_item_value(item, "first_page")

    if first_page:
        detail_url = reverse(
            "archive:detail",
            kwargs={"source_id": source_id, "start_page": first_page},
        )
    else:
        detail_url = reverse("archive:detail", kwargs={"source_id": source_id})
    return context["request"].build_absolute_uri(detail_url)


def _add_common_fields(item):
    """Return common metadata fields from Solr object."""
    return {
        "title": _get_item_value(item, "title"),
        "au": _get_item_value(item, "author"),
        "date": _get_item_value(item, "pub_date"),
        "pub": _get_item_value(item, "publisher"),
        "pub_place": _get_item_value(item, "pub_place"),
    }


def _add_full_work_fields(item, existing_data):
    """Return fields specific to full works."""
    return {
        "rft_val_fmt": "info:ofi/fmt:kev:mtx:book",
        "genre": "book",
        "title": existing_data.get("title"),
        "place": _get_item_value(item, "pub_place"),
    }


def _add_excerpt_fields(item, existing_data):
    """Return fields specific to excerpts."""
    fields = {
        "rft_val_fmt": "info:ofi/fmt:kev:mtx:book",
        "genre": "bookitem",
        "atitle": existing_data.get("title"),
        "btitle": _get_item_value(item, "book_journal"),
        "place": _get_item_value(item, "pub_place"),
    }

    # Add page information for excerpts if available
    first_page = _get_item_value(item, "first_page")
    if first_page:
        last_page = _get_item_value(item, "last_page")
        fields.update(
            {
                "spage": first_page,
                "epage": last_page or first_page,
                "pages": f"{first_page}-{last_page}"
                if last_page and last_page != first_page
                else first_page,
            }
        )

    return fields


def _add_article_fields(item, existing_data):
    """Return fields specific to articles."""
    fields = {
        "rft_val_fmt": "info:ofi/fmt:kev:mtx:journal",
        "genre": "article",
        "atitle": existing_data.get("title"),
        "jtitle": _get_item_value(item, "book_journal"),
        "volume": _get_item_value(item, "enumcron"),
    }

    # Add page information for articles if available
    first_page = _get_item_value(item, "first_page")
    if first_page:
        last_page = _get_item_value(item, "last_page")
        fields.update(
            {
                "spage": first_page,
                "epage": last_page or first_page,
                "pages": f"{first_page}-{last_page}"
                if last_page and last_page != first_page
                else first_page,
            }
        )

    return fields


def _add_work_type_specific_fields(item, existing_data, work_type_str):
    """Return fields based on work type."""
    if work_type_str == "full-work":
        return _add_full_work_fields(item, existing_data)
    elif work_type_str == "excerpt":
        return _add_excerpt_fields(item, existing_data)
    elif work_type_str == "article":
        return _add_article_fields(item, existing_data)
    return {}


@register.simple_tag(takes_context=True)
def coins_data(context, item):
    """Generate COinS metadata dictionary for Zotero from Solr results."""
    work_type_str = _get_item_value(item, "work_type", "full-work")
    absolute_url = _generate_absolute_url(context, item)

    data = {
        "ctx_ver": "Z39.88-2004",
        "rft_id": absolute_url,
    }

    # Add common fields first
    common_fields = _add_common_fields(item)
    data.update(common_fields)

    # Add work-type-specific fields
    work_type_fields = _add_work_type_specific_fields(item, data, work_type_str)
    data.update(work_type_fields)

    # Add rft. prefix to fields (except those already prefixed)
    coins_fields = {
        f"rft.{k}" if not k.startswith(("rft", "ctx_ver")) else k: v
        for k, v in data.items()
        if v is not None  # Skip None values
    }

    return coins_fields


@register.filter
def coins_encode(coins_data):
    """Convert COinS metadata dictionary to encoded HTML span element."""
    if not coins_data:
        return ""

    title_parts = []
    for key, value in coins_data.items():
        if value:
            encoded_value = urlencode({"": str(value)})[1:]
            title_parts.append(f"{key}={encoded_value}")

    title_attr = "&amp;".join(str(part) for part in title_parts)
    return format_html('<span class="Z3988" title="{}"></span>', title_attr)
