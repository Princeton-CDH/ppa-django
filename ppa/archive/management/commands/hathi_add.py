"""
**hathi_add** is a custom manage command for adding new HathiTrust
records to the local database *and* to the local pairtree datastore.
For records that are already in the local pairtree, use **hathi_import**.

Example usage::

    # add items by id on the command line
    python manage.py hathi_add htid1 htid2 htid3
    # add items by one id per line in a text file
    python manage.py --file path/to/idfile.txt

"""

import logging
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.template.defaultfilters import pluralize

from ppa.archive.util import HathiImporter

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Import HathiTrust digitized items into PPA to be managed and searched"""

    help = __doc__

    hathi_pairtree = {}
    stats = None
    script_user = None
    options = {}
    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    def add_arguments(self, parser):
        parser.add_argument(
            "htids",
            nargs="*",
            help="Optional list of specific volumes to add by HathiTrust id.",
        )
        parser.add_argument(
            "--file",
            "-f",
            help="Filename with a list of HathiTrust ids to add (one per line).",
        )

    def handle(self, *args, **kwargs):
        # disconnect signal handler for on-demand indexing, for efficiency
        # (index in bulk after an update, not one at a time)

        self.verbosity = kwargs.get("verbosity", self.v_normal)
        self.options = kwargs

        self.stats = defaultdict(int)
        # determine ids from command line and/or input file
        htids = self.ids_to_process()

        # create importer and filter out existing ids
        htimporter = HathiImporter(htids)
        htimporter.filter_existing_ids()

        # report on any requested ids that are already in the db
        if htimporter.existing_ids:
            self.stats["skipped"] += len(htimporter.existing_ids)
            if self.verbosity >= self.v_normal:
                self.stdout.write(
                    "Skipping ids already present: %s"
                    % ", ".join(htimporter.existing_ids.keys())
                )

        # add records for all remaining ids
        htimporter.add_items(log_msg_src="via hathi_add script")

        # count and report on errors
        output_results = htimporter.output_results()
        for htid, status in htimporter.results.items():
            # report errors to stderr
            if status not in (HathiImporter.SUCCESS, HathiImporter.SKIPPED):
                self.stderr.write("%s - %s" % (htid, output_results[htid]))
                self.stats["error"] += 1
            # report success unless verbosity below default
            if status == HathiImporter.SUCCESS:
                if self.verbosity >= self.v_normal:
                    self.stdout.write("%s - successfully added" % htid)

        # get totals for added works & pages
        self.stats["created"] = len(htimporter.imported_works)
        self.stats["pages"] = sum(
            digwork.page_count for digwork in htimporter.imported_works
        )

        # index works and pages for newly added items
        htimporter.index()

        summary = (
            "\nProcessed {:,d} item{}."
            + "\nAdded {:,d}; skipped {:,d}; {:,d} error{}; imported {:,d} page{}."
        )
        summary = summary.format(
            self.stats["total"],
            pluralize(self.stats["total"]),
            self.stats["created"],
            self.stats["skipped"],
            self.stats["error"],
            pluralize(self.stats["error"]),
            self.stats["pages"],
            pluralize(self.stats["pages"]),
        )
        self.stdout.write(summary)

    def ids_to_process(self):
        """Determine Hathi ids to be processed. Checks list of ids
        on the command line and file if specified."""
        htids = self.options["htids"]
        # if id file is specified, get ids from the file
        if self.options["file"]:
            with open(self.options["file"]) as idfile:
                # add all non-empty lines with whitespace removed
                htids.extend(
                    [line.strip() for line in idfile.readlines() if line.strip()]
                )

        self.stats["total"] = len(htids)
        return htids
