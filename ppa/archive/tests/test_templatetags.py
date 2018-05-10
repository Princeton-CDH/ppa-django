from unittest.mock import Mock

from django.http import QueryDict

from ppa.archive.templatetags.ppa_tags import dict_item, querystring_replace, \
    page_image_url


def test_dict_item():
    # no error on not found
    assert dict_item({}, 'foo') is None
    # string key
    assert dict_item({'foo': 'bar'}, 'foo') is 'bar'
    # integer key
    assert dict_item({13: 'lucky'}, 13) is 'lucky'
    # integer value
    assert dict_item({13: 7}, 13) is 7


def test_querystring_replace():
    mockrequest = Mock()
    mockrequest.GET = QueryDict('query=saussure')
    context = {'request': mockrequest}
    # replace when arg is not present
    args = querystring_replace(context, page=1)
    # preserves existing args
    assert 'query=saussure' in args
    # adds new arg
    assert 'page=1' in args

    mockrequest.GET = QueryDict('query=saussure&page=2')
    args = querystring_replace(context, page=3)
    assert 'query=saussure' in args
    # replaces existing arg
    assert 'page=3' in args
    assert 'page=2' not in args

    # handle repeating terms
    mockrequest.GET = QueryDict('language=english&language=french')
    args = querystring_replace(context, page=10)
    assert 'language=english' in args
    assert 'language=french' in args
    assert 'page=10' in args


def test_page_image_url():
    # simple page id
    item_id = "mdp.39015031594768"
    page_id = "00000029"
    page_seq = 29
    width = 180
    img_url = page_image_url(item_id, page_id, width)
    print(img_url)
    assert img_url.startswith("https://babel.hathitrust.org/cgi/imgsrv/image?")
    assert img_url.endswith('image?id=%s;seq=%s;width=%s' % (item_id, page_seq, width))

    # page id with non-numeric characters
    item_id = 'uc1.c2608792'
    page_id = 'UCAL_C2608792_00000009'
    page_seq = 9
    img_url = page_image_url(item_id, page_id, width)
    assert img_url.endswith('image?id=%s;seq=%s;width=%s' % (item_id, page_seq, width))
