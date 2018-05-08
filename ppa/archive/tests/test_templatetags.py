from ppa.archive.templatetags.ppa_tags import dict_item


def test_dict_item():
    # no error on not found
    assert dict_item({}, 'foo') is None
    # string key
    assert dict_item({'foo': 'bar'}, 'foo') is 'bar'
    # integer key
    assert dict_item({13: 'lucky'}, 13) is 'lucky'
    # integer value
    assert dict_item({13: 7}, 13) is 7