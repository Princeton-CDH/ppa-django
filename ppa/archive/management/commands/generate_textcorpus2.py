"""
**generate_textcorpus** is a custom manage command to generate a plain
text corpus from Solr.  It should be run *after* content has been indexed
into Solr via the **index** manage command.
"""

import os
import jsonlines
from django.core.management.base import BaseCommand
from ppa.archive.models import DigitizedWork
from parasolr.django import SolrQuerySet
from progressbar import progressbar

class Command(BaseCommand):
    """Custom manage command to generate a text corpus from text indexed in Solr"""

    PAGE_OUTPUT_FIELDS = {'id','source_id','group_id_s','content','order','label','tags'}

    def add_arguments(self, parser):
        parser.add_argument(
            "--path", required=True, help="Directory path to save corpus file(s)."
        )

    def iter_solr(self, nsize=10, item_type='page'):
        i=0
        q=SolrQuerySet().search(item_type=item_type)
        total = q.count()
        for i in progressbar(range(0, total, nsize)):
            q.set_limits(i,i+nsize)
            yield from q

    def iter_pages(self):
        for d in self.iter_solr(item_type='page'):
            yield {k:v for k,v in d.items() if k in self.PAGE_OUTPUT_FIELDS}

    def iter_works(self):
        for d in self.iter_solr(item_type='work'):
            yield d

    def handle(self, *args, **options):
        path = options['path']
        os.makedirs(path, exist_ok=True)
        path_meta = os.path.join(path,'metadata.jsonl')
        path_texts = os.path.join(path,'pages.jsonl')
        with jsonlines.open(path_meta,'w') as of_meta:
            for d in self.iter_works():
                of_meta.write(d)
        with jsonlines.open(path_texts,'w') as of_meta:
            for d in self.iter_pages():
                of_meta.write(d)