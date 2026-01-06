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

    - Export data for publication (includes datapackage file) and validate:

        python manage.py generate_textcorpus --validate

    - Validate a previous export (all files must be present):

        python manage.py generate_textcorpus --validate-only --path ~/ppa_solr_corpus

Notes:

    - Default path is `ppa_corpus_{timestamp}` in the current working directory
    - Default batch size is 10,000 (Solr record iteration size, chosen
      based on performance.)

"""

import argparse
import csv
import json
import pathlib
import shutil
from collections.abc import Generator
from datetime import datetime

import orjsonl
from django.core.management.base import CommandError
from parasolr.django import SolrQuerySet
from progressbar import progressbar


from ppa.archive.models import DigitizedWork
from ppa.archive.management.commands import index_pages
from ppa.archive.solr import PageSearchQuerySet

DEFAULT_BATCH_SIZE = 10000
TIMESTAMP_FMT = "%Y-%m-%d_%H%M%S"


# dataset/management/command -> dataset
app_dir = pathlib.Path(__file__).parent.parent.parent
data_package_path = app_dir / "ppa_datapackage.json"


class Command(index_pages.Command):
    """
    Custom manage command to generate a text corpus from text indexed in Solr.
    """

    # extends index pages command to re-use logic for checking
    # page count discrepancies between db and Solr index

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
        }
    }
    work_fields = [
        "work_id",
        "source_id",
        "record_id",
        "author",
        "title",
        "subtitle",
        "sort_title",
        "work_type",
        "book_journal",
        "volume",
        "pub_year",
        "pub_place",
        "publisher",
        "pages_orig",
        "pages_digital",
        "page_count",
        "collections",
        "cluster_id",
        "source",
        "source_url",
        "added",
        "updated",
    ]
    # dictionary of index data keys that need to be renamed
    work_indexdata_rename = {
        "group_id_s": "work_id",
        "cluster_id_s": "cluster_id",
        "pub_date": "pub_year",
        "work_type_s": "work_type",
        "source_t": "source",
        "enumcron": "volume",
        "book_journal_s": "book_journal",
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
            type=pathlib.Path,
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
        # check the data before exporting
        parser.add_argument(
            "--check",
            help="Check that work and page totals in Database and Solr match",
            action=argparse.BooleanOptionalAction,
            default=False,
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

    def work_metadata(self) -> Generator[dict[str, str | list[str] | int]]:
        """
        Returns a generator of dictionaries with work-level metadata.
        """
        # sort by id (index id = source id + first page), to match previous implementation
        for digwork in DigitizedWork.items_to_index().order_by(
            "source_id", "pages_orig"
        ):
            # use Solr index data as starting point
            work_data = digwork.index_data()
            # rename index data fields to output field names
            work_data = {
                self.work_indexdata_rename.get(key, key): val
                for key, val in work_data.items()
            }
            work_data.update(
                {
                    # override solr index cluster with cluster id name
                    "cluster_id": str(digwork.cluster) if digwork.cluster else None,
                    # override work type with display value instead of slugified version
                    "work_type": digwork.get_item_type_display(),
                    # add database fields not indexed in Solr
                    "record_id": digwork.record_id,
                    "pages_orig": str(digwork.pages_orig),  # convert from intspan
                    "pages_digital": str(digwork.pages_digital),  # convert from intspan
                    "page_count": digwork.page_count,
                    "added": digwork.added.isoformat(),  # convert from datetime
                    "updated": digwork.updated.isoformat(),  # convert from datetime
                }
            )

            # create a new dict based on defined field order; exclude empty values
            work_data = {
                field: work_data[field]
                for field in self.work_fields
                if work_data.get(field)
            }

            yield work_data

    # save pages
    def iter_pages(self):
        """
        Yield results from :meth:`iter_solr` with `item_type=page`
        """
        yield from self.iter_solr(item_type="page")

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
                # fieldnames are defined on the class
                writer = csv.DictWriter(csvfile, fieldnames=self.work_fields)
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
            self.path = pathlib.Path(f"ppa_corpus_{timestamp()}")

        self.path_works_json = self.path / "ppa_metadata.json"
        self.path_works_csv = self.path / "ppa_metadata.csv"
        jsonl_ext = "jsonl.gz" if options.get("gzip") else "jsonl"
        self.path_pages_json = self.path / f"ppa_pages.{jsonl_ext}"

        self.metadata_only = options.get("metadata_only", False)
        self.is_dry_run = options.get("dry_run")
        self.doclimit = options.get("doc_limit")
        self.verbosity = options.get("verbosity", self.verbosity)
        self.progress = options.get("progress")
        self.batch_size = options.get("batch_size", DEFAULT_BATCH_SIZE)
        self.check = options.get("check")
        self.query_set = SolrQuerySet()

    def check_workcount(self):
        """
        Check that works represented by pages indexed in Solr matches
        expected number of works in the database that will be included
        in the dataset.
        """
        # facet pages on group id and then count unique groups
        facets = (
            PageSearchQuerySet()
            .filter(item_type="page")
            .facet("group_id", limit=-1)
            .get_facets()
        )
        total_solr_page_works = len(facets.facet_fields["group_id"])
        total_works = DigitizedWork.items_to_index().count()
        if total_works == total_solr_page_works:
            self.stdout.write(
                self.style.SUCCESS(
                    "Total works in database matches works with "
                    + f"pages in Solr ({total_works:,})"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Total works in database does not match works with pages"
                    + f" in Solr: {total_works - total_solr_page_works:+}"
                )
            )

    def check_pagecount(self):
        """
        Check that the number of pages indexed in Solr matches
        expected number of pages for works in the database.
        """
        page_mismatches = self.get_digwork_page_count_mismatches()
        # if dict is empty, all page counts match
        if not page_mismatches:
            self.stdout.write(self.style.SUCCESS("No discrepancies in page counts"))
        else:
            total_work_mismatches = len(page_mismatches)
            plural = "s" if total_work_mismatches != 1 else ""
            self.stdout.write(
                self.style.WARNING(
                    f"{total_work_mismatches} work{plural} with page count"
                    + " difference between DB and Solr"
                )
            )
            # in increased verbosity mode, get_digwork_page_count_mismatches
            # reports on the specific works and the discrepancy

    def handle(self, *args, **options):
        self.set_params(*args, **options)

        # when requested, check totals for works and pages before exporting
        if self.check:
            self.check_workcount()
            self.check_pagecount()

        # ensure output path exists
        if not self.is_dry_run:
            if self.verbosity >= self.v_normal:
                self.stdout.write(f"Saving files in {self.path}")
            self.path.mkdir(exist_ok=True)

        # save metadata (always)
        print("***saving metadata")
        self.save_metadata()
        # save pages unless running in metadata-only mode
        if not self.metadata_only:
            self.save_pages()

        # copy datapackage file to output folder, unless running in
        #  metadata-only mode or dry-run
        if not self.metadata_only and not self.is_dry_run:
            # copy data package file to export dir (replaces if already present)
            export_datapackage = self.path / data_package_path.name
            shutil.copy(data_package_path, export_datapackage)
            # NOTE: pages path & compression in depends on gzip flag
            # alert user to update manually
            if self.path_pages_json.suffix != ".gz":
                self.stdout.write(
                    "NOTE: datapackage for pages must be updated manually "
                    + "(default: .gz + compression)"
                )


# helper func
def timestamp():
    """helper method to generate timestamp for use in output filename"""
    return datetime.now().strftime(TIMESTAMP_FMT)
