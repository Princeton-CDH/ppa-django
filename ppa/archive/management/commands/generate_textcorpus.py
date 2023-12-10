"""
**generate_textcorpus** is a custom manage command to generate a plain
text corpus from Solr.  It should be run *after* content has been indexed
into Solr via the **index** manage command.
"""

DEFAULT_BATCH_SIZE=10000

import os
import json
from django.core.management.base import BaseCommand
from ppa.archive.models import DigitizedWork
from parasolr.django import SolrQuerySet
from progressbar import progressbar
import logging
import gzip
import orjsonl
from functools import cached_property
from collections import deque

class Command(BaseCommand):
    """
    Custom manage command to generate a text corpus from text indexed in Solr.
    
    Examples:

        python manage.py generate_textcorpus --path ~/ppa_solr_corpus

        python manage.py generate_textcorpus --path ~/ppa_solr_corpus --dry-run
        
        python manage.py generate_textcorpus --path ~/ppa_solr_corpus --doc-limit 100000

        python manage.py generate_textcorpus --path ~/ppa_solr_corpus --batch-size 1000

    """

    # fields we want from pages, in solr syntax: newfieldname:oldfieldname
    PAGE_FIELDLIST = [
        'page_id:id',
        'work_id:group_id_s',
        'source_id:source_id',
        'page_num:order',
        'page_num_orig:label',
        'page_tags:tags',
        'page_text:content'
    ]

    
    # Argument parsing
    def add_arguments(self, parser):
        """
        Build CLI arguments for command.
        """

        # add --path argument for output storage
        parser.add_argument(
            "--path",
            required=True, 
            help="Directory path to save corpus file(s)."
        )
        
        # add --doc-limit argument (determines how many results to retrieve from solr)
        parser.add_argument(
            "--doc-limit",
            type=int,
            default=-1,
            help="Limit on the number of documents for corpus generation."
            "The default of -1 considers ALL documents.",
        )

        # add --batch-size argument (for solr querying)
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help="Number of docs to query from solr at one time",
        )

        # add --dry-run argument (don't save anything, just iterate)
        parser.add_argument(
            "--dry-run",
            action='store_true',
            help="Do not save anything, just iterate over solr",
        )



    #### SOLR ####

    @cached_property
    def query_set(self):
        """
        A cached representation of the query set; discourages opening multiple connections to database.
        """
        return SolrQuerySet()

    
    def iter_solr(self, item_type='page'):
        """
        Iterate over solr documents of a certain `item_type`.
        """

        # get query
        batch_size,lim = self.batch_size,self.doclimit
        qset=self.query_set.search(item_type=item_type).order_by('id')
        if item_type=='page': qset=qset.only(*self.PAGE_FIELDLIST)
        total = qset.count()
        if lim and int(total)>lim: total=lim
        if batch_size>total: batch_size=total

        # iterate with progress bar
        iterr = (
            result
            for step in range(0, total, batch_size)
            for result in qset[step:step+batch_size]
        )
        if self.progress:
            iterr = progressbar(iterr, max_value=total)
        yield from iterr


    def iter_works(self):
        """
        Simply calls iter_solr() with item_type=="work"
        """
        yield from self.iter_solr(item_type='work')
    
    # save pages
    def iter_pages(self):
        """
        Simply calls iter_solr() with item_type=="page"
        """
        yield from self.iter_solr(item_type='page')


    ### saving to file
    def save_metadata(self):
        """
        Save the work-level metadata as a json file
        """
        # get the data from solr
        data = list(self.iter_works())

        # save if not a dry run
        if not self.is_dry_run:
            with open(self.path_meta,'w') as of:
                json.dump(data, of, indent=2)

    def save_pages(self):
        """
        Save the page-level metadata as a jsonl file
        """
         ### save pages
        if self.is_dry_run:
            # iterate in place
            deque(self.iter_pages(), maxlen=0)
        else:
            # save to jsonl or jsonl.gz
            orjsonl.save(self.path_texts, self.iter_pages())




    ### running script

    def handle(self, *args, **options):
        """
        Run the command, generating metadata.jsonl and pages.jsonl
        """
        # options
        self.path = options['path']
        self.path_meta = os.path.join(self.path,'metadata.json')
        self.path_texts = os.path.join(self.path,'pages.jsonl.gz')
        self.is_dry_run = options['dry_run']
        self.doclimit = options['doc_limit'] if options['doc_limit']>0 else None
        self.progress = options['verbosity']>0
        self.batch_size = options['batch_size']

        # ensure path
        if not self.is_dry_run:
            os.makedirs(self.path, exist_ok=True)
        
        # save metadata
        self.save_metadata()

        # save pages
        self.save_pages()