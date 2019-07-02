"""
**generate_corpus** is a custom manage command to generate and serialize
a Gensim corpus from Solr.  It should be run *after* content has been indexed
into Solr via the **index** manage command.

The Corpus is serialized in the Matrix Market format (https://math.nist.gov/MatrixMarket/formats.html)
with a .mm extension, using the Gensim Topic Modelling library (https://radimrehurek.com/gensim)
Typically, an index corresponding to the .mm file is also saved by Gensim, with a .mm.index extension.

A dictionary corresponding to token IDs is also saved by default, using a .mm.dict extension.
By default, this is a pickled Gensim Dictionary object.
If the --dictionary-as-text flag is specified, then the dictionary is saved as a utf8-encoded and newline-separated
    file, where line number N contains the token with token_id N-1.
Saving the dictionary can be skipped by using the --no-dictionary option.

Additional document-level metadata found in the Solr Index is also saved by default, with .mm.metadata extension.
This is a csv file with a header row and one row per unique document found in the Solr index.
Saving the metadata can be skipped by using the --no-metadata option.

By default, _all_ documents found in the Solr index are serialized. This can be controlled using --doc-limit,
which denotes the maximum no. of documents to serialize.

For corpus generation, the following preprocessing options are available via the --preprocess flag:

    'lower' = Lower-cases words
    'strip_tags' = Strips HTML tags
    'strip_punctuation' = Strips punctuation
    'strip_multiple_whitespaces' = Collapses multiple whitespaces into one
    'strip_numeric' = Strips numeric characters
    'remove_stopwords' = Removes stopwords.
        Note that the set of default stopwords used by Gensim is from Stone, Denis, Kwantes (2010).
    'strip_short' = strip short words. The lower limit on word length used here is 3.
    'stem_text' = Use Porter Stemmer for word-normalization.

IMPORTANT - NO preprocessing filters are applied by default, but you will typically at least want to use 'lower'.
Multiple preprocessing filters can be applied (in order) by specifying multiple --preprocess flags.

Example usage::

    # Save all files to the 'data' folder, with bare-minimum preprocessing
    python manage.py generate_corpus --path data --preprocess lower --preprocess strip_tags

    # Restrict corpus to 1000 documents
    python manage.py generate_corpus --path data --doc-limit 1000 --preprocess lower --preprocess strip_tags

    # Don't generate dictionary; don't generate metadata
    python manage.py generate_corpus --path data --doc-limit 1000 --preprocess lower --no-dictionary --no-metadata

"""

import logging
import csv
from os import makedirs
import os.path
from progressbar import ProgressBar, NullBar

from gensim import corpora
from gensim.corpora.dictionary import Dictionary
from gensim.parsing.preprocessing import preprocess_string, strip_tags, strip_punctuation, \
    strip_multiple_whitespaces, strip_numeric, remove_stopwords, strip_short, stem_text

from django.core.management.base import BaseCommand

from ppa.archive.solr import get_solr_connection

logger = logging.getLogger(__name__)

PREPROCESS_FUNCTIONS = {
    'lower': lambda x: x.lower(),
    'strip_tags': strip_tags,
    'strip_punctuation': strip_punctuation,
    'strip_multiple_whitespaces': strip_multiple_whitespaces,
    'strip_numeric': strip_numeric,
    'remove_stopwords': remove_stopwords,
    'strip_short': strip_short,
    'stem_text': stem_text
}


class SolrCorpus:

    # Class attributes that rarely, if ever, need to change
    DOC_ID_FIELD = 'source_id'     # Solr field name for document identifier
    DOC_CONTENT_FIELD = 'content'  # Solr field name for document content
    PAGE_ORDER_FIELD = 'order'     # Solr field name for page ordering

    def __init__(self, name, client, collection, doc_limit=-1, preprocess_fns=None, pbar=True):
        """
        A class encapsulating a Solr Client specification, that yields Bag-of-Word vectors on iteration, and thus
            acts as a Gensim Corpus.

        :param name: A string name of this corpus. Used as a string prefix for generated files.
        :param client: A SolrClient.SolrClient object used to interface with Solr
        :param collection: A string representing the Solr collection name.
        :param doc_limit: Max no. of documents to process. The default of -1 means we process ALL documents found.
        :param preprocess_fns: A list of single-argument functions to use as preprocessors.
            See the module gensim.parsing.preprocessing for some typical preprocessing functions.
        :param pbar: A boolean indicating whether to display a progress bar during corpus generation.
        """
        self.name = name
        self.client = client
        self.collection = collection
        self.doc_limit = doc_limit
        self.preprocess_fns = preprocess_fns or []

        self.dictionary = Dictionary()

        # doc_id -> dict of k->v mappings
        # NOTE: We cannot use 'metadata' as GenSim mangles this attribute internally!
        self._metadata = {}

        # list of strings, populated on first doc retrieval
        self.metadata_field_names = None

        results = self.client.query(
            collection=self.collection,
            query={
                'q': '*:*',
                'facet': 'on',
                'rows': 0,
                'facet.field': SolrCorpus.DOC_ID_FIELD,
                'facet.limit': self.doc_limit
            }
        )

        """
        An OrderedDict of doc_id => page count mapping
        An OrderedDict is important here in case we want to save document-level metadata, in which case rows of
        metadata would be in the same order as the BoW-vectors returned by this object's iterator.
        """
        self.page_counts = results.get_facets()['source_id']
        self.doc_ids = self.page_counts.keys()
        self.doc_count = len(self.doc_ids)
        self.pbar = ProgressBar(redirect_stderr=True, max_value=self.doc_count) if pbar else NullBar()

    def __iter__(self):

        for doc_id in self.doc_ids:

            if doc_id not in self.page_counts:
                logger.warning('Unknown page count for doc {}. Skipping.'.format(doc_id))
                continue

            result = self.client.query(
                collection=self.collection,
                query={
                    'q': '{}:{}'.format(SolrCorpus.DOC_ID_FIELD, doc_id),
                    'order': '{} asc'.format(SolrCorpus.PAGE_ORDER_FIELD),
                    'rows': self.page_counts[doc_id]
                }
            )

            metadata_docs = [d for d in result.docs if d['item_type'] == 'work']
            n_metadata_docs = len(metadata_docs)
            if n_metadata_docs > 0:
                if n_metadata_docs > 1:
                    logger.warning('Multiple metadata records found for doc ID {}. Using the first.'.format(doc_id))

                metadata_doc = metadata_docs[0]
                self._metadata[doc_id] = {k: v for k, v in metadata_doc.items()}
                if self.metadata_field_names is None:
                    self.metadata_field_names = list(metadata_doc.keys())
            else:
                logger.warning('No metadata record found for doc ID {}.'.format(doc_id))

            # filter out pages that have no content; combine all pages into one string
            fulltext = ' '.join(list(
                filter(
                    None,
                    (doc.get(SolrCorpus.DOC_CONTENT_FIELD) for doc in result.docs if doc['item_type'] == 'page')
                )
            ))
            fulltext = preprocess_string(fulltext, filters=self.preprocess_fns)

            yield self.dictionary.doc2bow(fulltext, allow_update=True)
            self.pbar.update(self.pbar.value + 1)

    def _save_dictionary(self, filepath, as_text=False):
        """
        Save dictionary at a specified path, either as a picked Gensim Dictionary object, or a .txt file
        :param filepath: File path for saved dictionary
        :param as_text: Whether to save as a plaintext file, where the 0-indexed line number denotes the token id.
        :return: None
        """
        if as_text:
            with open(filepath, 'w', encoding='utf8') as f:
                f.writelines([self.dictionary[i] + '\n' for i in range(len(self.dictionary))])
        else:
            self.dictionary.save(filepath)

    def _save_metadata(self, filepath):
        if self.metadata_field_names is None:
            raise RuntimeError('Unable to determine metadata field names!')

        with open(filepath, 'w', encoding='utf8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(self.metadata_field_names)  # header row

            for doc_id in self.doc_ids:
                metadata = self._metadata[doc_id]
                writer.writerow([metadata.get(field_name) for field_name in self.metadata_field_names])

    def save(self, path, save_dict=True, save_dict_as_text=False, save_metadata=False):
        if not os.path.isdir(path):
            makedirs(path)
        corpus_path = os.path.join(path, '{}.mm'.format(self.name))

        # There's no way to completely turn off the progress ticker for Gensim serialize - we simply set it's
        # frequency to one more than the no. of documents we have, so it will effectively be shut off.
        corpora.MmCorpus.serialize(corpus_path, self, progress_cnt=self.doc_count+1)

        if save_dict:
            self._save_dictionary(corpus_path + '.dict', as_text=save_dict_as_text)
        if save_metadata:
            self._save_metadata(corpus_path + '.metadata')


class Command(BaseCommand):

    def _preprocess_fn(self, name):
        if name in PREPROCESS_FUNCTIONS:
            return PREPROCESS_FUNCTIONS[name]
        else:
            # argparse automatically traps any TypeError and ValueError exceptions and converts them to a simple error
            # message for the user.
            raise ValueError

    def add_arguments(self, parser):
        parser.add_argument(
            '--path', required=True,
            help='Directory path to save corpus file(s).')
        parser.add_argument(
            '--name', default='corpus',
            help='Name prefix to use for all saved corpus file(s).')

        parser.add_argument(
            '--doc-limit', type=int, default=-1,
            help='Limit on the number of documents for corpus generation. The default of -1 considers ALL documents.')
        parser.add_argument(
            '--no-dictionary', action='store_true',
            help='Do not save corpus dictionary.')
        parser.add_argument(
            '--dictionary-as-text', action='store_true',
            help='If saving dictionary, save as a plaintext file.')
        parser.add_argument(
            '--no-metadata', action='store_true',
            help='Do not save corpus metadata.')
        parser.add_argument(
            '--no-progress', action='store_true',
            help='Do not display progress bar to track the status of the command.')
        parser.add_argument(
            '--preprocess', action="append", type=self._preprocess_fn,
            help='Preprocessing filter(s) to apply. One of {}. Multiple filters can be applied (in order) by adding \
                multiple --preprocess flags.'.format(' / '.join(PREPROCESS_FUNCTIONS.keys())))

    def handle(self, *args, **options):
        client, collection = get_solr_connection()

        corpus = SolrCorpus(
            name=options['name'],
            client=client,
            collection=collection,
            doc_limit=options['doc_limit'],
            preprocess_fns=options['preprocess'],
            pbar=not options['no_progress']
        )

        corpus.save(
            options['path'],
            save_dict=not options['no_dictionary'],
            save_dict_as_text=options['dictionary_as_text'],
            save_metadata=not options['no_metadata']
        )
