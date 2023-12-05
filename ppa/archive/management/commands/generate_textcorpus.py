"""
**generate_textcorpus** is a custom manage command to generate a plain
text corpus from Solr.  It should be run *after* content has been indexed
into Solr via the **index** manage command.
"""

import os
import json
from django.core.management.base import BaseCommand
from ppa.archive.models import DigitizedWork
from parasolr.django import SolrQuerySet
from progressbar import progressbar
import logging
import gzip


class Command(BaseCommand):
    """Custom manage command to generate a text corpus from text indexed in Solr"""

    # fields we want from pages
    PAGE_FIELDLIST = [
        'page_id:id',
        'work_id:group_id_s',
        'source_id:source_id',
        'page_num:order',
        'page_num_orig:label',
        'page_tags:tags',
        'page_text:content'
    ]

    def add_arguments(self, parser):
        """Build CLI arguments: --path and --doc-limit"""
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
        parser.add_argument(
            "--batch",
            type=int,
            default=100,
            help="Number of docs to save at one time",
        )

    def iter_solr(self, batch_size=1000, item_type='page', lim=None, progress=True):
        """
        Iterate over solr documents of a certain `item_type`
        """
        i=0
        qset = SolrQuerySet()
        

        def get_query(order=True):
            q=qset.search(item_type=item_type)
            if order: q=q.order_by('id')
            if item_type=='page': q=q.only(*self.PAGE_FIELDLIST)
            return q

        q=get_query(order=False)
        total = q.count()
        if lim and int(total)>lim: total=lim
        iterr = range(0, total, batch_size)
        if progress:
            iterr = progressbar(iterr)
        for step in iterr:
            q=get_query(order=True)
            q.set_limits(step, step+batch_size)
            for d in q:
                yield d

    def handle(self, *args, **options):
        """
        Run the command, generating metadata.jsonl and pages.jsonl
        """
        # options
        path = options['path']
        doclimit = options['doc_limit'] if options['doc_limit']>0 else None
        progress = options['verbosity']>0
        batch_size = options['batch']
        by_batch = batch_size > 1

        # paths
        os.makedirs(path, exist_ok=True)
        path_meta = os.path.join(path,'metadata.json')
        path_texts = os.path.join(path,'pages.jsonl.gz')
        
        # save metadata
        def iter_works():
            yield from self.iter_solr(
                item_type='work',
                lim=doclimit,
                progress=progress,
                # batch_size=batch_size if by_batch else 1000
            )

        output_ld = list(iter_works())
        with open(path_meta,'w') as of:
            json.dump(output_ld, of, indent=2)
        

        # save pages
        def iter_pages():
            yield from self.iter_solr(
                item_type='page',
                lim=doclimit,
                progress=progress,
                # batch_size=batch_size if by_batch else 1000
            )
        ### save pages
        if not by_batch:
            with gzip.open(path_texts,'wt',encoding='utf-8') as of:
                for d in iter_pages():
                    of.write(json.dumps(d)+'\n')
        else:    
            with gzip.open(path_texts,'wt',encoding='utf-8') as of:
                batch=[]
                
                def save_batch():
                    outstr='\n'.join(json.dumps(d) for d in batch) + '\n'
                    of.write(outstr)

                for i,d in enumerate(iter_pages()):
                    if i and not i%batch_size:
                        save_batch()
                        batch=[]
                    batch.append(d)

                if batch:
                    save_batch()