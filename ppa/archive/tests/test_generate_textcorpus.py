from unittest.mock import patch
import json
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
import pandas as pd
import os

# mock results for acet query used to get document IDs and page counts
mock_solr_facets = {"group_id_s": {"doc_1": 2, "doc_2": 1}}

# mock result for solr document data
mock_solr_docs = [
    # The first record has item_type='work' and contains metadata for the
    # document
    {"item_type": "work", "pub_year": 1863, "group_id_s":"doc_1"},
    # If multiple metadata rows are found, the first one (above) is used
    # Subsequent records have item_type='page', page-order specified by
    # 'order', with content in 'content'
    {
        "item_type": "page",
        "order": 1,
        "content": "Four score and seven years ago our fathers brought forth"
        " on this continent, a new nation, ",
        "group_id_s":"doc_1",
        "label":'i'
    },
    {
        "item_type": "page",
        "order": 2,
        "content": "conceived in Liberty, and dedicated to the proposition"
        " that all men are created equal.",
        "group_id_s":"doc_1",
        "label":'ii'
    },



    {"item_type": "work", "pub_year": "unknown","group_id_s":"doc_2"},
    {
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
        mock_qs.get_results.return_value = mock_solr_docs
        mock_qs.get_facets.return_value.facet_fields = mock_solr_facets

        yield mock_qs


def test_save(tmpdir, patched_solr_queryset):
    call_command("generate_textcorpus", "--path", tmpdir.dirpath())
    metadata_file = tmpdir.dirpath("metadata.csv")
    assert metadata_file.check()
    dfmeta = pd.read_csv(metadata_file)
    assert len(dfmeta) == 2

    tdir=tmpdir.dirpath('texts')
    fns=os.listdir(tdir)
    assert len(fns) == 2

    print(fns)
    fn1=os.path.join(tdir,fns[0])
    fn2=os.path.join(tdir,fns[1])
    with open(fn1) as f: ld1=json.load(f)
    with open(fn2) as f: ld2=json.load(f)

    assert len(ld1)==2
    assert len(ld2)==1

    assert all(all(bool(v) for k,v in d.items()) for d in ld1)
    assert all(all(bool(v) for k,v in d.items()) for d in ld2)
        





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
