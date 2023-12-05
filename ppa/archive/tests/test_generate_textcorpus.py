from unittest.mock import patch
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
import os
import json

# mock result for solr document data
mock_solr_docs = [
    # The first record has item_type='work' and contains metadata for the
    # document
    {"item_type": "work", "pub_year": 1863, "group_id_s":"doc_1", 'id':'yyy'},
    {"item_type": "work", "pub_year": "unknown","group_id_s":"doc_2", 'id':'xxx'},
    # If multiple metadata rows are found, the first one (above) is used
    # Subsequent records have item_type='page', page-order specified by
    # 'order', with content in 'content'
    {
        'id':'yyy.001',
        "item_type": "page",
        "order": 1,
        "content": "Four score and seven years ago our fathers brought forth"
        " on this continent, a new nation, ",
        "group_id_s":"doc_1",
        "label":'i',
    },
    {
        'id':'xxx.001',
        "item_type": "page",
        "order": 2,
        "content": "conceived in Liberty, and dedicated to the proposition"
        " that all men are created equal.",
        "group_id_s":"doc_1",
        "label":'ii'
    },



    {
        'id':'xxx.001',
        "item_type": "page",
        "order": 3,
        "content": "!!!!!",
        "group_id_s":"doc_2",
        "label":"2"
    },
]


@pytest.fixture
def patched_solr_queryset(mock_solr_queryset):
    # local fixture that uses parasolr queryset mock
    # and patches in test docs & facets
    mock_qs = mock_solr_queryset()
    with patch(
        "ppa.archive.management.commands.generate_textcorpus.SolrQuerySet", new=mock_qs
    ) as mock_queryset_cls:
        mock_qs = mock_queryset_cls.return_value
        mock_qs.only.return_value.count.return_value = len(mock_solr_docs)
        mock_qs.only.return_value.get_results.return_value = mock_solr_docs
        yield mock_qs


def test_save(tmpdir, patched_solr_queryset):
    call_command("generate_textcorpus", "--path", tmpdir.dirpath(),'--doc-limit',10)
    print(os.listdir(tmpdir.dirpath()))
    
    metadata_file = tmpdir.dirpath("metadata.json")
    pages_file = tmpdir.dirpath("pages.jsonl")
    assert metadata_file.check()
    with open(metadata_file) as f: meta=json.load(f)
    assert len(meta) == 10

    def numlines(fngz):
        with gzip.open(fngz,'rt',encoding='utf-8') as f:
            return sum(1 for ln in f)
    
    assert numlines(pages_file) > 10
        





def test_invalid_preprocess_flags(tmpdir, patched_solr_queryset):
    # Flags that are not supported
    with pytest.raises(CommandError):
        call_command(
            "generate_textcorpus", "--path", tmpdir.dirpath(), "--doc-limit","one"
        )

    with pytest.raises(CommandError):
        call_command(
            "generate_textcorpus", "--woops","huh"
        )
