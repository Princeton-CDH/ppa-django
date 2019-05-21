import os.path
from tempfile import TemporaryDirectory
import pytest
from unittest.mock import patch, Mock
from django.core.management import call_command


@pytest.fixture
def temp_dirname():
    with TemporaryDirectory() as temp_dir:
        yield temp_dir


# ------------------------------
# Mock objects
# ------------------------------

# A Mock of JSON data returned by a typical Solr query
mock_solr_query = Mock()

# A facet query is used to get document IDs and their page counts
mock_solr_query.get_facets.return_value = {
    "source_id": {
        "doc_1": 2,
        "doc_2": 2
    }
}

# A regular query is used to get document level data
mock_solr_query.docs = [
    # The first record has item_type='work' and contains metadata for the document
    {
        'item_type': 'work',
        'pub_year': 1863
    },
    # Subsequent records have item_type='page', page-order specified by 'order', with content in 'content'
    {
        'item_type': 'page',
        'order': 1,
        'content': 'Four score and seven years ago our fathers brought forth on this continent, a new nation, '
    },
    {
        'item_type': 'page',
        'order': 2,
        'content': 'conceived in Liberty, and dedicated to the proposition that all men are created equal.'
    }
]

# A Mock of a SolrClient object that provides a Mock query on demand
mock_solr_client = Mock()
mock_solr_client.query.return_value = mock_solr_query

# ------------------------------


@patch('ppa.archive.solr.get_solr_connection')
def test_dictionary(mock_get_solr_connection, temp_dirname):
    mock_get_solr_connection.return_value = (mock_solr_client, 'mock_collection')

    call_command('gensim_serialize', '--path', temp_dirname)
    dictionary_file = os.path.join(temp_dirname, 'corpus.mm.dict')
    assert os.path.exists(dictionary_file)

    tokens = open(dictionary_file, 'r').readlines()
    assert len(tokens) == 29  # 29 unique tokens


@patch('ppa.archive.solr.get_solr_connection')
def test_dictionary_with_preprocessing(mock_get_solr_connection, temp_dirname):
    mock_get_solr_connection.return_value = (mock_solr_client, 'mock_collection')

    call_command('gensim_serialize', '--path', temp_dirname, '--preprocess', 'strip_short')
    dictionary_file = os.path.join(temp_dirname, 'corpus.mm.dict')
    assert os.path.exists(dictionary_file)

    tokens = open(dictionary_file, 'r').readlines()
    assert len(tokens) == 25  # 25 unique tokens with length>=3


@patch('ppa.archive.solr.get_solr_connection')
def test_metadata_file(mock_get_solr_connection, temp_dirname):
    mock_get_solr_connection.return_value = (mock_solr_client, 'mock_collection')

    call_command('gensim_serialize', '--path', temp_dirname, '--preprocess', 'strip_short')
    metadata_file = os.path.join(temp_dirname, 'corpus.mm.metadata')
    assert os.path.exists(metadata_file)

    lines = open(metadata_file, 'r').readlines()
    # 3 lines - header + metadata for doc_1 + metadata for doc_2
    assert len(lines) == 3

    # Header line with metadata field names. Note that we cannot rely on the order
    assert set(lines[0].rstrip('\n').split(',')) == {'item_type', 'pub_year'}

    # The actual rows with metadata - our mock object returns the same metadata for both documents
    assert set(lines[1].rstrip('\n').split(',')) == {'work', '1863'}
    assert set(lines[2].rstrip('\n').split(',')) == {'work', '1863'}
