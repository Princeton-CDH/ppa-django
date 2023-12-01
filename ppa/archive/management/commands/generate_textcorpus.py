"""
**generate_textcorpus** is a custom manage command to generate a plain
text corpus from Solr.  It should be run *after* content has been indexed
into Solr via the **index** manage command.
"""

import os
import json
from django.core.management.base import BaseCommand
from parasolr.django import SolrQuerySet
from collections import defaultdict, OrderedDict
import logging
from tqdm import tqdm
from typing import Tuple
from contextlib import contextmanager
import logging

class SolrCorpus:
    """Custom class to generate a text corpus from Solr"""

    # Class attributes that rarely, if ever, need to change
    DOC_ID_FIELD = "group_id_s"  # Solr field name for document identifier (not source_id, which is same across excerpts)
    PAGE_ORDER_FIELD = "order"  # Solr field name for page ordering
    OUTPUT_DOC_FIELDS = dict(
        page_num_orig = 'label',
        page_num_digi = 'order',
        page_text = 'content',
    )
    PAGE_ID_FIELD = 'page_id'
    WORK_ID_FIELD = 'work_id'
    PAGE_NUM_FIELD = 'page_num_orig'
    PAGE_SORT_FIELD = 'page_num_digi'

    def __init__(self, path, doc_limit=-1):
        """
        A class encapsulating a Solr Client specification which yields
       metadata and page data for PPA documents.

        :param path: A string to a path for the corpus output.
        :param doc_limit: Max no. of documents to process. The default of -1
            means we process ALL documents found.
        """
        # root path for corpus
        self.path = path

        # limit docs queried
        self.doc_limit = doc_limit

        # subsequent paths
        self.path_texts = os.path.join(self.path,'texts')
        self.path_metadata = os.path.join(self.path,'metadata.json')
        
        # query to get initial results
        results = SolrQuerySet().facet(self.DOC_ID_FIELD, limit=self.doc_limit)
        # store page counts and doc ids
        self.page_counts = results.get_facets().facet_fields[self.DOC_ID_FIELD]
        self.doc_ids = self.page_counts.keys()
        self.doc_count = len(self.doc_ids)
    
    @staticmethod
    def _get_id(doc_id:str) -> str:
        """Method to make a file-safe version of a document ID"""
        return doc_id.replace('/','|')

    def _get_meta_pages(self, doc_id:str) -> Tuple[dict,list]:
        """Get metadata (dictionary) and pages (list of dictionaries) for a given document"""
        
        # get file safe work_id
        work_id = self._get_id(doc_id)

        # query
        result = (
            SolrQuerySet()
            .search(**{self.DOC_ID_FIELD: doc_id})
            .order_by(self.PAGE_ORDER_FIELD)
        )

        # populate the result cache with number of rows specified
        docs = [
            doc
            for doc in result.get_results(rows=self.page_counts[doc_id])
            if doc[self.DOC_ID_FIELD]==doc_id
        ]

        # find the metadata doc
        metadata_docs = [d for d in docs if d["item_type"] == "work"]
        assert len(metadata_docs)==1
        meta = {self.WORK_ID_FIELD:work_id, **metadata_docs[0]}

        # find the pages docs
        page_docs = [d for d in docs if d["item_type"] == "page"]

        # transform into new dictionary with keys in `self.PAGE_ID_FIELD` and `self.OUTPUT_DOC_FIELDS`
        pages = [self._transform_doc(doc,meta) for doc in page_docs]

        # make sure sorted by numeric page num (i.e. "digital")
        pages.sort(key=lambda page: page[self.PAGE_SORT_FIELD])
        return meta, pages

    def _transform_doc(self,doc:dict,meta:dict) -> dict:
        """Reformat document dictionary"""

        # get new dictionary
        odoc={
            key_new:doc.get(key_orig,'')
            for key_new,key_orig in (
                self.OUTPUT_DOC_FIELDS.items()
            )
        }

        # return with page id
        return {
            self.PAGE_ID_FIELD:f'{meta[self.WORK_ID_FIELD]}_{odoc[self.PAGE_NUM_FIELD]}',
            **odoc
        }
    
    def _save_doc(self,doc_id:str) -> Tuple[str,dict]:
        """Save document pages as json and return filename along with document's metadata"""

        # get metadata and pages for this doc
        meta,pages = self._get_meta_pages(doc_id)

        # if pages, save json
        if pages:
            filename = os.path.join(self.path_texts, meta[self.WORK_ID_FIELD]+'.json')
            os.makedirs(self.path_texts,exist_ok=True)
            with open(filename,'w') as of:
                json.dump(pages, of, indent=2)
        
        # otherwise, returned filename is blank to indicate no file saved
        else:
            filename=''
        
        return filename,meta


    def save(self):
        """Save the generated corpus text and metadata to files on disk"""

        # save docs and gather metadata
        metadata=[]
        pdesc='Saved text to'
        pbar=tqdm(total=self.doc_count, desc=f'{pdesc}: ...')
        for doc_id in self.doc_ids:
            # get saved filename and found metadata for this document
            fn,meta = self._save_doc(doc_id)

            # if we saved, update progress bar desc
            if fn: pbar.set_description(f'{pdesc}: {fn}')

            # tick
            pbar.update()

            # add this doc's meta to metadata
            metadata.append(meta)
        pbar.close()

        # save metadata csv
        with open(self.path_metadata,'w') as of:
            json.dump(metadata, of, indent=2)
        print(f'Saved metadata to: {self.path_metadata}')





@contextmanager
def logging_disabled(highest_level=logging.CRITICAL):
    """Quick way to suppress solr logs as we iterate. Taken from https://gist.github.com/simon-weber/7853144"""
    previous_level = logging.root.manager.disable
    logging.disable(highest_level)
    try: yield
    finally: logging.disable(previous_level)




class Command(BaseCommand):
    """Custom manage command to generate a text corpus from text indexed in Solr"""

    def add_arguments(self, parser):
        parser.add_argument(
            "--path", required=True, help="Directory path to save corpus file(s)."
        )

        parser.add_argument(
            "--doc-limit",
            type=int,
            default=-1,
            help="Limit on the number of documents for corpus generation."
            "The default of -1 considers ALL documents.",
        )


    def handle(self, *args, **options):
        with logging_disabled():
            SolrCorpus(
                path=options["path"],
                doc_limit=options["doc_limit"],
            ).save()