"""
**generate_textcorpus** is a custom manage command to generate a plain
text corpus from Solr with accompanying work-level metadata.  Because
it relies on Solr for full-text content, it should be run *after*
page contents have been indexed in Solr via the **index_pages** manage command.

The full text corpus is generated from Solr; it does not include content
for suppressed works or their pages (note that this depends on Solr
content being current).

Example usage:

    - Default behavior::

        python manage.py generate_textcorpus

    - Specify output path::

        python manage.py generate_textcorpus --path ~/ppa_solr_corpus

    - Dry run (do not create any files or folders)::

        python manage.py generate_textcorpus --dry-run

    - Partial run (save only N rows, for testing)::

        python manage.py generate_textcorpus --doc-limit 100

    - Suppress progress bar and increase verbosity:

        python manage.py generate_textcorpus --no-progress --verbosity 2

Notes:

    - Default path is `ppa_corpus_{timestamp}` in the current working directory
    - Default batch size is 10,000 (Solr record iteration size;
      this default was chosen for performance based on testing.)

"""

from collections.abc import Generator
import argparse
import os
from datetime import datetime
import json
import csv

from django.core.management.base import BaseCommand, CommandError
from parasolr.django import SolrQuerySet
from progressbar import progressbar
import orjsonl

from ppa.archive.models import DigitizedWork


DEFAULT_BATCH_SIZE = 10000
TIMESTAMP_FMT = "%Y-%m-%d_%H%M"


class Command(BaseCommand):
    """
    Custom manage command to generate a text corpus from text indexed in Solr.
    """

    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    # fields to return from Solr; output_name: solr_field_name
    FIELDLIST = {
        "page": {
            "id": "id",
            "work_id": "group_id_s",
            "order": "order",
            "label": "label",
            "tags": "tags",
            "text": "content",
        },
        "work": {
            "work_id": "group_id_s",
            "source_id": "source_id",
            "cluster_id": "cluster_id_s",
            "title": "title",
            "author": "author",
            "pub_year": "pub_date",
            "publisher": "publisher",
            "pub_place": "pub_place",
            "collections": "collections",
            "work_type": "work_type_s",
            "source": "source_t",
            "source_url": "source_url",
            "sort_title": "sort_title",
            "subtitle": "subtitle",
            "volume": "enumcron",
            "book_journal": "book_journal_s",
        },
    }

    #: multivalue delimiter for CSV output (only applies to collections)
    multival_delimiter = ";"
    #: optional behavior to generate metadata export only
    metadata_only = False

    # Argument parsing
    def add_arguments(self, parser):
        """
        Configure additional CLI arguments
        """
        # add --path argument for output
        parser.add_argument(
            "--path",
            help="Directory path to save corpus file(s). Defaults to ./ppa_corpus_{timestamp}",
            default=None,
        )

        # add --doc-limit argument (determines how many results to retrieve from solr)
        parser.add_argument(
            "--doc-limit",
            type=int,
            default=None,
            help="Limit the number of documents for corpus generation. "
            "By default, includes ALL documents.",
        )

        # add --batch-size argument (for solr querying)
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help="Number of docs to query from solr at one time",
        )

        # control compression of pages jsonl output (enabled by default)
        parser.add_argument(
            "--gzip",
            help="Save pages as compressed or uncompressed "
            "(ppa_pages.jsonl or ppa_pages.jsonl.gz) [default: %(default)s]",
            action=argparse.BooleanOptionalAction,
            default=True,
        )
        # add option to skip pages and output metadata only
        parser.add_argument(
            "--metadata-only",
            action="store_true",
            help="Only generate metadata export (skip page export)",
            default=False,
        )
        # add --dry-run argument (don't save anything, just iterate)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not save anything, just iterate over solr",
        )

        # control progress bar display (on by default)
        parser.add_argument(
            "--progress",
            help="Show progress",
            action=argparse.BooleanOptionalAction,
            default=True,
        )

    #### SOLR ####

    def iter_solr(self, item_type="page"):
        """
        Returns a generator Solr documents for the requested `item_type`
        (page or work).
        """
        # filter to the requested item type, order by id,
        # and return the configured set of fields
        qset = (
            self.query_set.filter(item_type=item_type)
            .order_by("id")
            .only(**self.FIELDLIST[item_type])
        )

        # get the total count for this query
        total = qset.count()
        if not total:
            raise CommandError(f"No {item_type} records found in Solr.")

        # if a doc limit is requested, decrease the total to pull from Solr
        if self.doclimit:
            total = min(total, self.doclimit)

        # define a generator to iterate solr with
        batch_iterator = (
            result
            for step in range(0, total, self.batch_size)
            for result in qset[
                step : (step + self.batch_size)
                if (step + self.batch_size) < total
                else total
            ]
        )

        # if progress bar is enabled, wrap the generator
        if self.progress:
            batch_iterator = progressbar(
                batch_iterator, max_value=total, prefix=f"Exporting {item_type}s: "
            )

        # yield from this generator
        yield from batch_iterator

    def work_metadata(self) -> Generator[dict[str, str | list[str]]]:
        """
        Returns a generator of dictionaries with work-level metadata.
        """
        indexdata_to_fields = {val: key for key, val in self.FIELDLIST["work"].items()}

        # sort by id (index id = source id + first page), to match previous implementation
        for digwork in DigitizedWork.items_to_index().order_by(
            "source_id", "pages_orig"
        ):
            # use Solr index data as starting point
            work_data = digwork.index_data()
            # use index data to fields dict to filter and rename index data
            work_data = {
                indexdata_to_fields[key]: val
                for key, val in work_data.items()
                if key in indexdata_to_fields
            }
            # override solr index cluster with cluster id name
            work_data["cluster_id"] = str(digwork.cluster) if digwork.cluster else None
            # filter out any empty values
            work_data = {key: val for key, val in work_data.items() if val}

            yield work_data

    # save pages
    def iter_pages(self):
        """
        Yield results from :meth:`iter_solr` with `item_type=page`
        """
        yield from self.iter_solr(item_type="page")

    def prep_metadata(self, data: Generator | list) -> Generator:
        # generate lookup dict for work item type slug to display
        pass  # define this on digwork
        # use slugify for work_type; store once and lookup by display

    #     @property
    # def work_type(self):
    #     """Work type formatted for COinS metadata (matches Solr field format)."""
    #     return self.get_item_type_display().lower().replace(" ", "-")

    def metadata_for_csv(self, data: Generator | list) -> Generator:
        """
        Takes a list or iterator of metadata records and yields a version
        ready for output to CSV: converts list field (collections) into
        a delimited string.
        """
        for row in data:
            record = row.copy()  # make a copy; don't modify the original
            # convert list field to delimited string
            record["collections"] = self.multival_delimiter.join(record["collections"])
            yield record

    ### saving to file
    def save_metadata(self):
        """
        Save the work-level metadata as a json file
        """
        # get work-level metadata
        # convert to a list so we can output twice
        data = list(self.work_metadata())

        # save if not a dry run
        if not self.is_dry_run:
            # save data as json
            with open(self.path_works_json, "w") as of:
                json.dump(data, of, indent=2)

            # save data as csv
            with open(self.path_works_csv, "w", newline="") as csvfile:
                # fieldnames are set on the class
                writer = csv.DictWriter(
                    csvfile, fieldnames=self.FIELDLIST["work"].keys()
                )
                writer.writeheader()
                writer.writerows(self.metadata_for_csv(data))

    def save_pages(self):
        """
        Save the page-level data as a jsonl file
        """
        ### save pages
        if self.is_dry_run:
            # consume the generator
            list(self.iter_pages())
        else:
            # save to jsonl or jsonl.gz
            orjsonl.save(self.path_pages_json, self.iter_pages())

    ### running script

    def set_params(self, *args, **options):
        """
        Run the command, generating metadata.jsonl and pages.jsonl
        """
        # options
        self.path = options.get("path")
        if not self.path:
            self.path = os.path.join(f"ppa_corpus_{nowstr()}")

        self.path_works_json = os.path.join(self.path, "ppa_metadata.json")
        self.path_works_csv = os.path.join(self.path, "ppa_metadata.csv")
        jsonl_ext = "jsonl.gz" if options.get("gzip") else "jsonl"
        self.path_pages_json = os.path.join(self.path, f"ppa_pages.{jsonl_ext}")
        self.metadata_only = options.get("metadata_only", False)
        self.is_dry_run = options.get("dry_run")
        self.doclimit = options.get("doc_limit")
        self.verbosity = options.get("verbosity", self.verbosity)
        self.progress = options.get("progress")
        self.batch_size = options.get("batch_size", DEFAULT_BATCH_SIZE)
        self.query_set = SolrQuerySet()

    def handle(self, *args, **options):
        self.set_params(*args, **options)

        # ensure output path exists
        if not self.is_dry_run:
            if self.verbosity >= self.v_normal:
                print(f"Saving files in {self.path}")
            os.makedirs(self.path, exist_ok=True)

        # save metadata
        self.save_metadata()

        # save pages unless running in metadata-only mode
        if not self.metadata_only:
            self.save_pages()


# helper func
def nowstr():
    """helper method to generate timestamp for use in output filename"""
    return datetime.now().strftime(TIMESTAMP_FMT)
