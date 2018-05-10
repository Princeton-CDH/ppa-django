import re

from django.template.defaulttags import register


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


#: regular expression to extract page sequence from page order
#: (could contain other content, but should end with numbers)
PAGE_REQUENCE_RE = re.compile(r'[^\d]*(\d+)$')


@register.simple_tag
def page_image_url(item_id, page, width):
    '''Generate a page image url based on an item id, page sequence label,
    and desired width. Currently HathiTrust specific.'''
    page_sequence = int(PAGE_REQUENCE_RE.search(page).group(1))
    return "https://babel.hathitrust.org/cgi/imgsrv/image?id={};seq={};width={}" \
        .format(item_id, page_sequence, width)
