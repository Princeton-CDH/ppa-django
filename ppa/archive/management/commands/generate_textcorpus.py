"""
**generate_textcorpus** is a custom manage command to generate a plain
text corpus from Solr.  It should be run *after* content has been indexed
into Solr via the **index** manage command.

Assumptions:
    * No suppressed works from PPA exist in the solr index
    * The "source_t" field exists in solr index, is a list, 
        but contains only entry (it will be ["Gale"] or ["Hathi"])
    


Examples:

    python manage.py generate_textcorpus --path ~/ppa_solr_corpus

    python manage.py generate_textcorpus --path ~/ppa_solr_corpus --dry-run

    python manage.py generate_textcorpus --path ~/ppa_solr_corpus --doc-limit 100000

    python manage.py generate_textcorpus --path ~/ppa_solr_corpus --batch-size 1000

"""
import os
from datetime import datetime
import json
import csv
from django.core.management.base import BaseCommand
from parasolr.django import SolrQuerySet
from progressbar import progressbar
import orjsonl
from collections import deque

DEFAULT_BATCH_SIZE = 10000


class Command(BaseCommand):
    """
    Custom manage command to generate a text corpus from text indexed in Solr.
    """

    # fields we want from pages, in solr syntax: newfieldname:oldfieldname
    PAGE_FIELDLIST = {
        "id": "id",
        "work_id": "group_id_s",
        "num": "order",
        "num_orig": "label",
        "tags": "tags",
        "text": "content",
    }

    WORK_FIELDLIST = {
        "work_id": "group_id_s",
        "source_id": "source_id",
        "cluster_id": "cluster_id_s",
        "title": "title",
        "author": "author_exact",
        "pub_year": "pub_date",
        "publisher": "publisher",
        "pub_place": "pub_place",
        "collections": "collections_exact",
        "work_type": "work_type_s",
        "source": "source_t",
        "source_url": "source_url",
        "sort_title": "sort_title",
        "subtitle": "subtitle",
    }

    # Argument parsing
    def add_arguments(self, parser):
        """
        Build CLI arguments for command.
        """

        # add --path argument for output storage
        parser.add_argument(
            "--path",
            help="Directory path to save corpus file(s)."
            "Defaults to ./ppa_corpus_{timestamp}",
            default=None,
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
            "--uncompressed",
            action="store_true",
            help="Save as ppa_pages.jsonl instead of ppa_pages.jsonl.gz",
        )

        # add --dry-run argument (don't save anything, just iterate)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not save anything, just iterate over solr",
        )

    #### SOLR ####

    def iter_solr(self, item_type="page"):
        """
        Iterate over solr documents of a certain `item_type`.
        """

        # get params
        batch_size, lim = self.batch_size, self.doclimit

        # search for this item type, order by id
        qset = self.query_set.filter(item_type=item_type).order_by("id")

        # if we're looking for pages, rename those fields
        if item_type == "page":
            qset = qset.only(**self.PAGE_FIELDLIST)
        elif item_type == "work":
            qset = qset.only(**self.WORK_FIELDLIST)

        # get the total count for this query
        total = qset.count()

        # if we want fewer than that, decrease "total"
        # (this has the effect of pulling from solr only what we need,
        # since we limit how many rows we pull by this amount)
        if lim and total > lim:
            total = lim

        # if total smaller than batch size, decrease batch size
        if batch_size > total:
            batch_size = total

        # define a generator to iterate solr with
        batch_iterator = (
            result
            for step in range(0, total, batch_size)
            for result in qset[step : step + batch_size]
        )

        # if progress bar wanted, tack one on
        if self.progress:
            batch_iterator = progressbar(batch_iterator, max_value=total)

        # yield from this generator, progress bar or no
        yield from batch_iterator

    def iter_works(self):
        """
        Simply calls `.iter_solr()` with `item_type` as `'work'`
        """
        for d in self.iter_solr(item_type="work"):
            # source does not need to be a list, will only be one
            # see module docstring for more info
            d["source"] = d["source"][0]

            # yield now
            yield d

    # save pages
    def iter_pages(self):
        """
        Simply calls `.iter_solr()` with `item_type` as `'page'`
        """
        yield from self.iter_solr(item_type="page")

    ### saving to file
    def save_metadata(self):
        """
        Save the work-level metadata as a json file
        """
        # get the data from solr
        data = list(self.iter_works())

        # save if not a dry run
        if not self.is_dry_run:
            # save json
            with open(self.path_meta, "w") as of:
                json.dump(data, of, indent=2)

            # save csv
            with open(self.path_meta_csv, "w", newline="") as csvfile:
                # fieldnames we already know
                fieldnames = list(self.WORK_FIELDLIST.keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)

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
        self.path = options["path"]
        if not self.path:
            self.path = os.path.join(f"ppa_corpus_{nowstr()}")

        self.path_meta = os.path.join(self.path, "ppa_metadata.json")
        self.path_meta_csv = os.path.join(self.path, "ppa_metadata.csv")
        self.uncompressed = options["uncompressed"]
        self.path_texts = os.path.join(
            self.path, "ppa_pages.jsonl" + ("" if self.uncompressed else ".gz")
        )
        self.is_dry_run = options["dry_run"]
        self.doclimit = options["doc_limit"] if options["doc_limit"] > 0 else None
        self.verbose = self.progress = options["verbosity"] > 0
        self.batch_size = options["batch_size"]
        self.query_set = SolrQuerySet()

        # ensure path
        if not self.is_dry_run:
            if self.verbose:
                print(f"saving PPA text corpus to: {self.path}")
            os.makedirs(self.path, exist_ok=True)

        # save metadata
        self.save_metadata()

        # save pages
        self.save_pages()


# helper func
def nowstr():
    return datetime.now().strftime("%Y-%m-%d_%H%M")
