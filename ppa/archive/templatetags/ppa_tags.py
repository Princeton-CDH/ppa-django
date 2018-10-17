import re

from django.template.defaultfilters import stringfilter
from django.template.defaulttags import register
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

import json


@register.filter
def dict_item(dictionary, key):
    ''''Template filter to allow accessing dictionary value by variable key.
    Example use::

        {{ mydict|dict_item:keyvar }}
    '''
    return dictionary.get(key, None)


@register.simple_tag(takes_context=True)
def querystring_replace(context, **kwargs):
    '''Template tag to simplify retaining querystring parameters
    when paging through search results with active filters.
    Example use:

        <a href="?{% querystring_replace page=paginator.next_page_number %}">
    '''
    # borrowed as-is from derrida codebase
    # inspired by https://stackoverflow.com/questions/2047622/how-to-paginate-django-with-other-get-variables

    # get a mutable copy of the current request
    querystring = context['request'].GET.copy()
    # update with any parameters passed in
    # NOTE: needs to *set* fields rather than using update,
    # because QueryDict update appends to field rather than replacing
    for key, val in kwargs.items():
        querystring[key] = val
    # return urlencoded query string
    return querystring.urlencode()

#: Base url for HathiTrust assets
HATHI_BASE_URL = 'https://babel.hathitrust.org/cgi'

@register.simple_tag
def page_url(item_id, order):
    '''Generate a link to HathiTrust for an individual page
    '''
    return '{}/pt?id={};view=1up;seq={}'.format(HATHI_BASE_URL, item_id, order)

@register.simple_tag
def page_image_url(item_id, page, width):
    '''Generate a page image url based on an item id, page sequence label,
    and desired width. Currently HathiTrust specific.'''
    return '{}/imgsrv/image?id={};seq={};width={}' \
        .format(HATHI_BASE_URL, item_id, page, width)


#: regular expression to identify open and close <em> tags in solr
#: highlighting snippets
EM_TAG_RE = re.compile(r'(</?em>)')


@register.filter(needs_autoescape=True)
@stringfilter
def solr_highlight(value, autoescape=True):
    '''Filter to render solr highlighting snippets for display.  Marks
    open and close <em> tags as safe and escapes all other text.'''

    # use conditional escape per django documentation
    # https://docs.djangoproject.com/en/1.11/howto/custom-template-tags/#filters-and-auto-escaping
    if autoescape:
        esc = conditional_escape
    else:
        esc = lambda x: x

    # split the text on em tags; mark em tags as safe and
    # escape everything else
    return mark_safe(''.join([
        mark_safe(part) if EM_TAG_RE.match(part) else esc(part)
        for part in EM_TAG_RE.split(value)
    ]))


@register.filter(name='json')
def json_dumps(data):
    return mark_safe(json.dumps(data))
