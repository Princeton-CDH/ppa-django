from django.core.paginator import Paginator
from django.http import HttpRequest
from django.template.loader import get_template


def test_pagination_snippet():

    pagination_tpl = get_template('archive/snippets/pagination.html')
    # initiate paginator with simple array, one item per page for testing
    # 5 pages of results only
    paginator = Paginator(range(5), per_page=1)
    # current page = 1
    ctx = {'page_obj': paginator.page(1), 'request': HttpRequest()}
    content = pagination_tpl.render(ctx)

    # current page should be present and marked active
    assert '<a title="page 1" class="ui active basic button" href="?page=1">1</a>' in content
    # no rel=previous link
    assert '<a name="previous page" title="previous page" rel="prev"' not in content
    # rel=next goes to page 2
    assert '<a name="next page" title="next page" rel="next" class="ui icon basic button" href="?page=2">' in content
    # goes up to page 5
    assert 'href="?page=5">5</a>' in content
    # no ellpsis
    assert '<span>...</span>' not in content

    # current page = 3
    ctx['page_obj'] = paginator.page(3)
    content = pagination_tpl.render(ctx)
    # next and prev both present
    assert '<a name="previous page" title="previous page" rel="prev" class="ui icon basic button" href="?page=2">' in content
    assert '<a name="next page" title="next page" rel="next" class="ui icon basic button" href="?page=4">' in content
    # no ellpsis
    assert '<span>...</span>' not in content

    # paginator with large set of results
    paginator = Paginator(range(100), per_page=1)
    # current page is 2
    ctx['page_obj'] = paginator.page(2)
    content = pagination_tpl.render(ctx)

    # displays up to page 5
    assert 'href="?page=5">5</a>' in content
    # displays link to last page
    assert 'href="?page=100">100</a>' in content
    # not the one before
    assert 'href="?page=99">99</a>' not in content
    # includes one ellipsis
    assert content.count('<span>...</span>') == 1

    # middle of large range
    ctx['page_obj'] = paginator.page(50)
    content = pagination_tpl.render(ctx)
    # next and prev both present
    assert '<a name="previous page" title="previous page" rel="prev" class="ui icon basic button" href="?page=49">' in content
    assert '<a name="next page" title="next page" rel="next" class="ui icon basic button" href="?page=51">' in content
    # first and last
    assert ' href="?page=1">1' in content
    assert ' href="?page=100">100' in content
    # includes two ellipses
    assert content.count('<span>...</span>') == 2
    # current page, marked active
    assert '<a title="page 50" class="ui active basic button" href="?page=50">50</a>' in content
    # two before and after
    assert ' href="?page=48">48' in content
    assert ' href="?page=49">49' in content
    assert ' href="?page=51">51' in content
    assert ' href="?page=52">52' in content

    # end of large range
    ctx['page_obj'] = paginator.page(100)
    content = pagination_tpl.render(ctx)
    # no rel=next link
    assert '<a name="next page" title="next page" rel="next"' not in content
    # first page
    assert ' href="?page=1">1' in content
    # one ellipsis only
    assert content.count('<span>...</span>') == 1
    # includes last 5
    assert ' href="?page=96">96' in content

