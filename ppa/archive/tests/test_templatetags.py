from unittest.mock import Mock

from django.http import QueryDict

from ppa.archive.templatetags.ppa_tags import dict_item, querystring_replace


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