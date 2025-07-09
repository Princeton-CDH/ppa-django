import re

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

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
    """Extract last page number from a page range like '25-30' or '25'"""
    if not page_range:
        return ""
    parts = page_range.split("-")
    return parts[-1].strip() if len(parts) > 1 else parts[0].strip()
