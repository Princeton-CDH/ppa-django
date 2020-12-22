from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
import pytest


# mock results for acet query used to get document IDs and page counts
mock_solr_facets = {
    "source_id": {
        "doc_1": 2,
        "doc_2": 2
    }
}

# mock result for solr document data
mock_solr_docs = [
    # The first record has item_type='work' and contains metadata for the
    # document
    {
        'item_type': 'work',
        'pub_year': 1863
    },
    # If multiple metadata rows are found, the first one (above) is used
    {
        'item_type': 'work',
        'pub_year': 'unknown'
    },
    # Subsequent records have item_type='page', page-order specified by
    # 'order', with content in 'content'
    {
        'item_type': 'page',
        'order': 1,
        'content': 'Four score and seven years ago our fathers brought forth'
                   ' on this continent, a new nation, '
    },
    {
        'item_type': 'page',
        'order': 2,
        'content': 'conceived in Liberty, and dedicated to the proposition'
                   ' that all men are created equal.'
    }
]


@pytest.fixture
def patched_solr_queryset(mock_solr_queryset):
    # local fixture that uses parasolr queryset mock
    # and patches in test docs & facets
    mock_qs = mock_solr_queryset()
    with patch('ppa.archive.management.commands.generate_corpus.SolrQuerySet',
               new=mock_qs) as mock_queryset_cls:
        mock_qs = mock_queryset_cls.return_value
        mock_qs.get_results.return_value = mock_solr_docs
        mock_qs.get_facets.return_value.facet_fields = mock_solr_facets

        yield mock_qs


def test_dictionary(tmpdir, patched_solr_queryset):
    call_command('generate_corpus', '--path', tmpdir.dirpath(),
                 '--dictionary-as-text')

    dictionary_file = tmpdir.dirpath('corpus.mm.dict')
    assert dictionary_file.check()

    with open(dictionary_file, 'r') as dictfile:
        tokens = dictfile.readlines()
    assert len(tokens) == 29  # 29 unique tokens


def test_dictionary_with_preprocessing(tmpdir, patched_solr_queryset):
    call_command('generate_corpus', '--path', tmpdir.dirpath(), '--preprocess',
                 'strip_short', '--dictionary-as-text')
    dictionary_file = tmpdir.dirpath('corpus.mm.dict')
    assert dictionary_file.check()

    with open(dictionary_file, 'r') as dictfile:
        tokens = dictfile.readlines()
    assert len(tokens) == 25  # 25 unique tokens with length>=3


def test_metadata_file(tmpdir, patched_solr_queryset):
    call_command('generate_corpus', '--path', tmpdir.dirpath(), '--preprocess',
                 'strip_short')
    metadata_file = tmpdir.dirpath('corpus.mm.metadata')
    assert metadata_file.check()

    with open(metadata_file, 'r') as mfile:
        lines = mfile.readlines()
    # 3 lines - header + metadata for doc_1 + metadata for doc_2
    assert len(lines) == 3

    # Header line with metadata field names. Note that we cannot rely on the
    # order
    assert set(lines[0].rstrip('\n').split(',')) == {'item_type', 'pub_year'}

    # The actual rows with metadata - our mock object returns the same metadata
    # for both documents
    assert set(lines[1].rstrip('\n').split(',')) == {'work', '1863'}
    assert set(lines[2].rstrip('\n').split(',')) == {'work', '1863'}


def test_invalid_preprocess_flags(tmpdir, patched_solr_queryset):
    # Flags that are not supported
    with pytest.raises(CommandError):
        call_command('generate_corpus', '--path', tmpdir.dirpath(),
                     '--preprocess', 'upper')
