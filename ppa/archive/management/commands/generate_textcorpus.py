"""
**generate_textcorpus** is a custom manage command to generate a plain
text corpus from Solr.  It should be run *after* content has been indexed
into Solr via the **index** manage command.

Vineet Bansal authored the parts of the code below that iterate over the Solr-
indexed corpus. Wouter Haverals authored the functions that preprocess the
returned page texts: cleaning OCR, rejoining lines, and other useful processes.

By default, *all* documents found in the Solr index are serialized.
This can be controlled using -`-doc-limit`,
which denotes the maximum no. of documents to serialize. This is especially
useful for development, or for sanity-testing your Solr installation.

For corpus generation, the following pre-processing options are available via
the `--preprocess` flag::

    # Lower-cases words
    'lower'
    # Strips HTML tags
    'strip_tags'
    # Strips punctuation
    'strip_punctuation'
    # Collapses multiple whitespaces into one
    'strip_multiple_whitespaces'
    # Strips numeric characters
    'strip_numeric'
    # Removes stopwords - Note that the set of default stopwords used by Gensim
    # is from Stone, Denis, Kwantes (2010).
    'remove_stopwords'
    # Strip short words. The lower limit on word length is 3.
    'strip_short'
    # Use Porter Stemmer for word-normalization.
    'stem_text'

IMPORTANT - NO preprocessing filters are applied by default, but you will
typically at least want to use `lower`.
Multiple preprocessing filters can be applied (in order) by specifying multiple
`--preprocess` flags.

Example usage::

    # Save all files to the 'data' folder, with bare-minimum preprocessing
    python manage.py generate_corpus --path data --preprocess lower
    --preprocess strip_tags

    # Restrict corpus to 1000 documents
    python manage.py generate_corpus --path data --doc-limit 1000
    --preprocess lower --preprocess strip_tags

    # Don't generate dictionary; don't generate metadata
    python manage.py generate_corpus --path data --doc-limit 1000
    --preprocess lower --no-dictionary --no-metadata

"""

import csv
import logging
logging.getLogger().handlers.clear()
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)


import os.path
from collections import OrderedDict
from os import makedirs
from pprint import pprint,pformat

from django.core.management.base import BaseCommand
from gensim import corpora
from gensim.corpora.dictionary import Dictionary
from parasolr.django import SolrQuerySet
from progressbar import NullBar, ProgressBar



### PREPROCESSING CODE ###

PATH_HERE = os.path.abspath(os.path.dirname(__file__))
PATH_REPO = os.path.abspath(os.path.join(
    PATH_HERE,
    '..', # management
    '..', # archive
    '..', # ppa
    '..' # ppa-django
))
PATH_REPO_DATA = os.path.join(PATH_REPO, 'data')
PATH_OCR_RULESETS = os.path.join(PATH_REPO_DATA, 'ocr_cleanup_rulesets')


# imports...
import os,sys,warnings,random
warnings.filterwarnings('ignore')
from functools import cache
from tqdm import tqdm
from sqlitedict import SqliteDict
import orjson,zlib
import pandas as pd
from intspan import intspan
import jsonlines
import multiprocessing as mp
mp.set_start_method('fork')

## ocr correction imports
import re
import wordfreq
import os
import json
import nltk
from nltk.tokenize import word_tokenize
import pandas as pd
from tqdm import tqdm
tqdm.pandas()
from collections import defaultdict
from difflib import SequenceMatcher
from functools import cached_property
from collections import Counter
import gzip
# nltk.download('punkt')



def tokenize_agnostic(txt):
    return re.findall(r"[\w']+|[.,!?; -—–'\n]", txt)

def untokenize_agnostic(l):
    return ''.join(l)

def remove_trailing_punctuation(word):
    """
    remove trailing punctuation and spaces
    don't remove the dash '-', as this might interfere with the function to repair broken words!
    Question: should we also remove punct at the beginning of the token...? Not doing that now.
    
    # small test
    word = "...example.,...! "
    clean_word = remove_trailing_punctuation(word)
    print(clean_word)
    """
    return re.sub(r'[\.,\?!"\')(:;`]+\s*$', '', word)






# process a list of word pairs, where each pair consists of an 'incorrect' word with a historic long 's' (ſ) and its 'correct' modern equivalent
# the script then replaces the historic long 's' (ſ) words with 'f', generates new word pairs
# ONLY if the newly generated f-word does NOT exist in the English language, we retain the word!! For this, we use language stats provided by wordfreq
# the resulting pairs are then written to the outfile, while pairs that exists -- with high frequency in English -- are written to a separate disregard_file
# i think this is clever, so i named the function accordingly :-)

def generate_clever_f_s_hack(source_file, output_file, disregard_file, skip_words=None, frequency_threshold=1e-6):
    if skip_words is None:
        skip_words = {'ſlip'}  # add specific words to skip here -- dunno if this is still useful, the file will capture most of these words

    unique_pairs = set()  # set to keep track of unique (incorrect f-word, correct s-word) pairs

    with open(source_file, 'r') as infile, open(output_file, 'w') as outfile, open(disregard_file, 'w') as disregard:
        # skip the title line of the infile
        next(infile)

        for line in infile:
            parts = line.strip().split('\t')
            if len(parts) < 3:
                continue

            incorrect, correct = parts[:2]
            # e.g.:
            # incorrect correct
            # moſt 	    most
            # muſt 	    must
            # ſo 	      so
            # ſome 	    some
            # ſee       see   etc.

            # strip leading/trailing spaces
            incorrect = incorrect.strip()
            correct = correct.strip()

            # remove trailing punctuation
            incorrect = remove_trailing_punctuation(incorrect)
            correct = remove_trailing_punctuation(correct)

            # replace 'ſ' with 'f' in the incorrect word
            f_incorrect = incorrect.replace('ſ', 'f')
            # e.g.:
            # incorrect correct
            # moft 	    most
            # muft 	    must
            # fo 	      so
            # fome 	    some
            # fee       see   etc.

            # skip if the incorrect word is in skip_words or already in pairs
            if f_incorrect in skip_words or (f_incorrect, correct) in unique_pairs:
                continue

            # check the frequency of the word
            word_frequency = wordfreq.word_frequency(f_incorrect.lower(), 'en')

            # skip if the word exists and its frequency is above the threshold
            if word_frequency > frequency_threshold:
                disregard.write(f"{f_incorrect}\t{correct}\n")
                #print(f'Word that exist with the f-spelling and we don\'t want to include: {f_incorrect}')
                # e.g.
                # Words that exist with the f-spelling and we don't want to include: fame
                # Words that exist with the f-spelling and we don't want to include: found    etc.
                continue

            # check if the generated word exists in English
            if word_frequency <= frequency_threshold:
                outfile.write(f"{f_incorrect}\t{correct}\n")
                unique_pairs.add((f_incorrect, correct))
                # e.g.
                # moft 	    most
                # muft 	    must
                # fo 	      so
                # fome 	    some    etc.

# apply
# generate_clever_f_s_hack(
#     source_file=os.path.join(PATH_OCR_RULESETS, "all_long_s_corrections_log.txt"),
#     output_file=os.path.join(PATH_OCR_RULESETS, "clever_f_ſ_hack.txt"),
#     disregard_file=os.path.join(PATH_OCR_RULESETS, "disregard_fſs_replacements.txt")
# )





@cache
def load_correction_rules(file_path = os.path.join(PATH_OCR_RULESETS, 'CorrectionRules.txt')):
    correction_rules = {}
    with open(file_path, 'r') as file:
        for line in file:
            parts = line.strip().split('\t')
            if len(parts) >= 2:
                incorrect, correct = parts[:2]
                correction_rules[incorrect] = correct
    return correction_rules


def correct_ocr_errors(text, correction_rules):
    corrections = 0
    for incorrect, correct in correction_rules.items():
        if incorrect in text:
            text = text.replace(incorrect, correct)
            corrections += 1
    return text, corrections

def rejoin_linebreaks(text, specific_linebreak_corrections):
    """
    function to addresses the issue of words that are split between two lines due to a line break, typically indicated by a hyphen
    the function rejoins such words
    """
    corrections = 0
    parts = text.split('-\n')
    corrected_text = parts[0]
    for part in parts[1:]:
        corrected_text_words = corrected_text.split()
        part_words = part.split()

        if corrected_text_words and part_words:  # check if both lists are not empty
            last_word_before_break = corrected_text_words[-1]
            first_word_after_break = part_words[0]

            # form the broken word and the corrected word
            broken_word = last_word_before_break + '-\n' + first_word_after_break
            corrected_word = last_word_before_break + first_word_after_break

            # log the correction (gets later written to the txt file)
            # specific_linebreak_corrections[broken_word + " \t " + corrected_word] += 1
            specific_linebreak_corrections.append((broken_word,corrected_word))

            corrected_text += part
            corrections += 1
        else:
            # if either part is empty or doesn't contain words, simply append a hyphen
            corrected_text += '-' + part

    return corrected_text, corrections

def replace_historic_long_s(text, long_s_corrections):
    """
    function to replaces the historic long 's' (ſ) with the regular 's'

    :text: text to be processed
    :long_s_corrections: dictionary to log specific corrections and their counts
    :return: tuple of processed text with long 's' replaced, and the number of corrections made
    """
    corrected_text = text.replace('ſ', 's')
    corrections = 0
    if corrected_text != text:
        words_with_long_s = set(text.split()) - set(corrected_text.split())
        for word in words_with_long_s:
            corrected_word = word.replace('ſ', 's')
            long_s_corrections.append((word,corrected_word))
            corrections += 1
    return corrected_text, corrections

@cache
def load_f_s_hack_corrections(file_path = os.path.join(PATH_OCR_RULESETS, "clever_f_ſ_hack.txt")):
    """
    little helper script to load the f-->s words (from generate_clever_f_s_hack) into a dict, for convenient lookup
    """
    correction_rules = {}
    with open(file_path, 'r') as file:
        for line in file:
            parts = line.strip().split()
            if len(parts) >= 2:
                incorrect, correct = parts[:2]
                correction_rules[incorrect] = correct
    return correction_rules

def process_headers(pages, remove_headers=True, similarity_threshold=80):
    """
    function to identifies and optionally removes running headers
    inspired by Ted Underwood's GREAT headerfinder script: https://github.com/tedunderwood/DataMunging/blob/master/runningheaders/HeaderFinder.py
    some changes made:
      - flexibility to remove headers or just identify them (just by setting the boolean value)
      - we don't explicitly handle roman numerals, the line comparison logic (combining str.isalpha and a threshold for fuzzy matching) should take care of it

    :pages: list of dicts, each representing a page with 'page_text'
    :remove_headers: bool, if set to True --> removes identified headers, otherwise just identifies them and wirtes them to the log
    :similarity_threshold: int, threshold for fuzzy matching to consider lines as similar (default 80 seems to work well)
    :return: list of pages with headers
    """
    identified_headers = []
    headers_set = set()

    def get_substantial_lines(page_text):
        """
        helper function: if the processed line contains less than 5 characters, or if the line consists solely of digits
        it is considered insubstantial and is skipped
        """
        lines = page_text.split('\n')
        substantial_lines = []
        for line in lines:
            if len(line.strip()) < 5 or line.strip().isdigit():
                continue
            substantial_lines.append(line)
            if len(substantial_lines) == 2:
                break
        return substantial_lines

    numpages = len(pages)
    iterr = range(numpages)
    iterr = tqdm(iterr, total=numpages, position=1, desc='Preprocessing headers',disable=True)
    for i in iterr:
        page = pages[i]
        if not 'corrections' in page: page['corrections']={}
        if not 'headers' in page['corrections']: page['corrections']['headers']=[]
        current_page_text = pages[i]['page_text']
        current_substantial_lines = get_substantial_lines(current_page_text)

        header_found = False

        # determine the range of pages to compare with
        start_index = max(0, i - 2)
        end_index = min(len(pages), i + 3)
        if i == len(pages) - 1:  # Special handling for the last page
            start_index = max(0, i - 2)  # Compare with pages before

        for j in range(start_index, end_index):
            if i == j:
                continue

            comparison_page_text = pages[j]['page_text']
            comparison_substantial_lines = get_substantial_lines(comparison_page_text)

            for current_line in current_substantial_lines:
                for comparison_line in comparison_substantial_lines:
                    # line comparison logic, considering possible page numbers
                    cleaned_current_line = ''.join(filter(str.isalpha, current_line))
                    cleaned_comparison_line = ''.join(filter(str.isalpha, comparison_line))

                    s = SequenceMatcher(None, cleaned_current_line, cleaned_comparison_line)
                    similarity = s.ratio() * 100

                    if similarity > similarity_threshold:
                        header_key = (i, current_line)
                        if header_key not in headers_set:
                            identified_headers.append(header_key)
                            headers_set.add(header_key)
                        if remove_headers:
                            header_found = True
                        break

                if header_found:
                    correx=(current_line,'')
                    if correx not in set(page['corrections']['headers']):
                        page['corrections']['headers'].append(correx)
                    lines_of_page = current_page_text.split('\n')
                    for idx, line in enumerate(lines_of_page):
                        if line.strip() == current_line.strip():
                            page['page_text_clean'] = '\n'.join(lines_of_page[idx+1:])
                            
                            break
                    break

    return pages



def cleanup_str(txt, use_nltk_tokenizer=False, **page_attrs):
    """
    Most of the cleanup occurs here. Can be called with a string or a string with page attributes
    """
    page_text = txt
    # dicts to store specific corrections and their counts
    specific_ocr_corrections = []
    specific_linebreak_corrections = []
    specific_long_s_corrections = []
    correction_rules = load_correction_rules()
    clever_f_s_hack_rules = load_f_s_hack_corrections()

    # add a dictionary for specific f ſ hack corrections
    specific_f_s_hack_corrections = []

    # counters for corrections
    linebreak_corrections = 0
    ocr_corrections = 0
    long_s_corrections = 0
    f_s_word_replacements = 0

    # rejoin line breaks before tokenization and log corrections
    page_text, corrections = rejoin_linebreaks(page_text, specific_linebreak_corrections)
    linebreak_corrections += corrections

    # apply correction for long 's'
    corrected_text, corrections = replace_historic_long_s(page_text, specific_long_s_corrections)
    long_s_corrections += corrections
    page_text = corrected_text

    # tokenization
    tokens = word_tokenize(page_text) if use_nltk_tokenizer else tokenize_agnostic(page_text)

    # apply OCR corrections on tokens and log corrections
    corrected_tokens = []
    for token in tokens:
        if token in correction_rules:
            corrected_token = correction_rules[token]
            ocr_corrections += 1
            specific_ocr_corrections.append((token,corrected_token))
        else:
            corrected_token = token
        corrected_tokens.append(corrected_token)

    # apply f-ſ-s hack corrections on tokens and log corrections
    for i, token in enumerate(corrected_tokens):
        if token in clever_f_s_hack_rules:
            corrected_token = clever_f_s_hack_rules[token]
            f_s_word_replacements += 1
            specific_f_s_hack_corrections.append((token,corrected_token))
            corrected_tokens[i] = corrected_token

    token_count = len(corrected_tokens)

    # convert corrected tokens back to text for further processing
    corrected_text = untokenize(corrected_tokens) if use_nltk_tokenizer else untokenize_agnostic(corrected_tokens)

    corrected_tokens_real = [x for x in corrected_tokens if any(y.isalpha() for y in x)]

    # create output dictionary
    def as_counts(l):
        return l
        # return dict(Counter(l))

    return {
        'page_text':page_text, 
        **page_attrs, 
        'page_text_clean':corrected_text, 
        # 'page_num_tokens':token_count,
        'page_tokens':corrected_tokens_real,
        'corrections': {
            'headers':as_counts(page_attrs.get('corrections',{}).get('headers',[])),
            'ocr':as_counts(specific_ocr_corrections),
            'linebreaks':as_counts(specific_linebreak_corrections),
            'long_s':as_counts(specific_long_s_corrections),
            'f_s':as_counts(specific_f_s_hack_corrections),
        }
    }



def cleanup_page(page_d):
    """
    Cleanup a page dictionary
    """
    txt=page_d.get('page_text_clean', page_d.get('page_text',''))
    odx=cleanup_str(txt, **page_d)
    return odx

def cleanup_pages(pages_ld):
    """
    Cleanup a list or dataframe of pages
    """
    logger.debug('processing headers')
    pages_ld = process_headers(pages_ld, remove_headers=True) # ideally, we want to set this later when calling the function
    
    logger.debug('processing headers')
    pages_ld = [cleanup_page(page_d) for page_d in tqdm(pages_ld,position=1,desc='Cleaning up pages',disable=True)]
    return pages_ld


















PREPROCESS_FUNCTIONS = OrderedDict(
    [
        # ("strip_short", strip_short),
        # ("strip_multiple_whitespaces", strip_multiple_whitespaces),
        # ("strip_punctuation", strip_punctuation),
        # ("strip_tags", strip_tags),
        # ("strip_numeric", strip_numeric),
        # ("lower", lambda x: x.lower()),
        # ("remove_stopwords", remove_stopwords),
        # ("stem_text", stem_text),
    ]
)


class SolrCorpus:
    """Custom class to generate a text corpus from Solr"""

    # Class attributes that rarely, if ever, need to change
    DOC_ID_FIELD = "source_id"  # Solr field name for document identifier
    DOC_CONTENT_FIELD = "content"  # Solr field name for document content
    PAGE_ORDER_FIELD = "order"  # Solr field name for page ordering
    OUTPUT_DOC_FIELDS = dict(
        work_cluster = 'cluster_id_s',
        work_group = 'group_id_s',
        work_source = 'source_id',
        page_id = '',
        page_orig = 'label',
        page_digital = 'order',
        page_text = 'content',
    )
    SOURCE_PAGE_ID = 'page_id'

    def __init__(self, name, doc_limit=-1, preprocess_fns=None, pbar=True):
        """
        A class encapsulating a Solr Client specification, that yields
        Bag-of-Word vectors on iteration, and thus acts as a Gensim Corpus.

        :param name: A string name of this corpus.
            Used as a string prefix for generated files.
        :param client: A SolrClient.SolrClient object used to interface with
            Solr
        :param collection: A string representing the Solr collection name.
        :param doc_limit: Max no. of documents to process. The default of -1
            means we process ALL documents found.
        :param preprocess_fns: A list of single-argument functions to use as
            preprocessors.
            See the module gensim.parsing.preprocessing for some typical
            preprocessing functions.
        :param pbar: A boolean indicating whether to display a progress bar
            during corpus generation.
        """
        self.name = name
        self.doc_limit = doc_limit

        if preprocess_fns is not None:
            if "ALL" in preprocess_fns:
                self.preprocess_fns = PREPROCESS_FUNCTIONS.values()
            else:
                self.preprocess_fns = [PREPROCESS_FUNCTIONS[k] for k in preprocess_fns]
        else:
            self.preprocess_fns = []

        self.dictionary = Dictionary()

        # doc_id -> dict of k->v mappings
        # NOTE: We cannot use 'metadata' as GenSim mangles this attribute!
        self._metadata = {}

        # list of strings, populated on first doc retrieval
        self.metadata_field_names = None

        # facet on document id to get counts of pages by work
        results = SolrQuerySet().facet(SolrCorpus.DOC_ID_FIELD, limit=self.doc_limit)

        """
        An OrderedDict of doc_id => page count mapping
        An OrderedDict is important here in case we want to save document-level
        metadata, in which case rows of metadata would be in the same order as
        the BoW-vectors returned by this object's iterator.
        """
        self.page_counts = results.get_facets().facet_fields["source_id"]
        self.doc_ids = self.page_counts.keys()
        self.doc_count = len(self.doc_ids)
        # if pbar:
        #     self.pbar = ProgressBar(
        #         redirect_stderr=True, max_value=self.doc_count, max_error=False
        #     )
        # else:
        #     self.pbar = NullBar()

    def __iter__(self):
        for doc_id in random.sample(self.doc_ids, len(self.doc_ids)):
            logger.debug(f'proceeding to doc id {doc_id}')
            if doc_id not in self.page_counts:
                logger.warning(
                    "Unknown page count for doc {}. Skipping.".format(doc_id)
                )
                continue
            logger.debug('querying solr')
            yield doc_id

    def _save_dictionary(self, filepath, as_text=False):
        """
        Save dictionary at a specified path, either as a picked Gensim
        Dictionary object, or a .txt file
        :param filepath: File path for saved dictionary
        :param as_text: Whether to save as a plaintext file, where the
        0-indexed line number denotes the token id.
        :return: None
        """
        if as_text:
            with open(filepath, "w", encoding="utf8") as f:
                f.writelines(
                    [self.dictionary[i] + "\n" for i in range(len(self.dictionary))]
                )
        else:
            self.dictionary.save(filepath)

    def _save_metadata(self, filepath):
        if self.metadata_field_names is None:
            raise RuntimeError("Unable to determine metadata field names!")

        with open(filepath, "w", encoding="utf8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(self.metadata_field_names)  # header row

            for doc_id in self.doc_ids:
                metadata = self._metadata[doc_id]
                writer.writerow(
                    [
                        metadata.get(field_name)
                        for field_name in self.metadata_field_names
                    ]
                )

    def save(self, path, save_dict=True, save_dict_as_text=False, save_metadata=False):
        """Save the generated corpus text and metadata to files on disk"""
        path_texts = os.path.join(path,'texts')
        path_metadata = os.path.join(path,'metadata.csv')
        if not os.path.isdir(path_texts): makedirs(path_texts)
        num_cpu=mp.cpu_count() // 2 if mp.cpu_count()>1 else 1
        pool = mp.Pool(num_cpu)
        tasks = []

        def iter_tasks():
            for i,obj in enumerate(self):
                yield (path_texts, self.page_counts, obj)

        for obj in iter_tasks():
            tasks.append(pool.apply_async(_do_save, (obj,)))
        
        # close the process pool
        filenames = []
        for task in tqdm(tasks,position=0,desc=f'Saving corpus [{num_cpu}x]'):
            res = task.get()
            filenames.append(res)
        
        return filenames


def _iter_group_pages(doc_id, page_counts):
    result = (
        SolrQuerySet()
        .search(**{SolrCorpus.DOC_ID_FIELD: doc_id})
        .order_by(SolrCorpus.PAGE_ORDER_FIELD)
    )
    # populate the result cache with number of rows specified
    docs = result.get_results(rows=page_counts[doc_id])
    logger.debug(f'found {len(docs)} documents')
    
    metadata_docs = [d for d in docs if d["item_type"] == "work"]
    logger.debug(f'found {len(metadata_docs)} metadata documents')

    page_docs = [d for d in docs if d["item_type"] == "page"]
    logger.debug(f'found {len(page_docs)} page documents')

    logger.debug(f'sorting page documents')
    page_docs.sort(key = lambda d: (d['source_id'], d['order']))
    work_page_docs = defaultdict(list)
    for pdoc in page_docs: 
        work_page_docs[pdoc['group_id_s']].append(pdoc)

    # filter out pages that have no content;
    # combine all pages into one string
    logger.debug(f'iterating over {len(work_page_docs)} groups')
    for group_id,source_pages in work_page_docs.items():
        logger.debug(f'proceeding to group {group_id} within document id {doc_id}')
        logger.debug(f'reformatting page document dictionaries')
        pages_ld = [
            _transform_doc(doc)
            for doc in source_pages
        ]
        assert all([
            (doc['work_group'] == group_id)
            for doc in pages_ld
        ])
        
        yield group_id,pages_ld



def _transform_doc(doc):
    odoc = OrderedDict({
        key_new:doc.get(key_orig,'')
        for key_new,key_orig in (
            SolrCorpus.OUTPUT_DOC_FIELDS.items()
        )
    })
    odoc[SolrCorpus.SOURCE_PAGE_ID] = f'{odoc["work_source"]}_{odoc["page_orig"]}'
    return odoc

def _do_save(obj):
    path_texts, page_counts, doc_id = obj
    filenames = []
    for group_id,pages_ld in _iter_group_pages(doc_id, page_counts):
        logger.debug(f'applying cleanup preprocessing')
        pages_ld = cleanup_pages(pages_ld)
        filename = os.path.join(path_texts, group_id.replace('/','|')+'.json')
        with open(filename,'w') as of:
            json.dump(pages_ld, of, indent=4, sort_keys=True)
        filenames.append(filename)
    return filenames
    

class Command(BaseCommand):
    """Custom manage command to generate a token corpus from text indexed in Solr"""

    def add_arguments(self, parser):
        parser.add_argument(
            "--path", required=True, help="Directory path to save corpus file(s)."
        )
        parser.add_argument(
            "--name",
            default="corpus",
            help="Name prefix to use for all saved corpus file(s).",
        )

        parser.add_argument(
            "--doc-limit",
            type=int,
            default=-1,
            help="Limit on the number of documents for corpus generation."
            "The default of -1 considers ALL documents.",
        )
        parser.add_argument(
            "--no-dictionary",
            action="store_true",
            help="Do not save corpus dictionary.",
        )
        parser.add_argument(
            "--dictionary-as-text",
            action="store_true",
            help="If saving dictionary, save as a plaintext file.",
        )
        parser.add_argument(
            "--no-metadata",
            action="store_true",
            default=False,
            help="Do not save corpus metadata.",
        )
        parser.add_argument(
            "--no-progress",
            action="store_true",
            help="Do not display progress bar to track the status of the" "command.",
        )
        parser.add_argument(
            "--preprocess",
            action="append",
            choices=list(PREPROCESS_FUNCTIONS.keys()) + ["ALL"],
            help="Pre-processing filter(s) to apply. Multiple filters can be"
            "applied (in order) by adding multiple --preprocess flags."
            "Use ALL to apply all pre-processing filters.",
        )

    def handle(self, *args, **options):
        corpus = SolrCorpus(
            name=options["name"],
            doc_limit=options["doc_limit"],
            preprocess_fns=options["preprocess"],
            pbar=not options["no_progress"],
        )

        filenames_saved = corpus.save(
            options["path"],
            save_dict=not options["no_dictionary"],
            save_dict_as_text=options["dictionary_as_text"],
            save_metadata=not options["no_metadata"],
        )

        print(f'Successfully saved {len(filenames_saved)} json files')
