"""
**adjust_excerpts** is a custom manage command to update
the digital page range for excerpts or articles. It requires a CSV file
with source id and original page range (to identify the correct record),
and the new digital page range.

The CSV must include:
    * source_id
    * pages_orig
    * new_pages_digital

Updated records are automatically indexed in Solr.
"""

import csv
import logging

import intspan
from django.conf import settings
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError

from ppa.archive.models import DigitizedWork

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Update digital page range for excerpted works."""

    help = __doc__

    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    def add_arguments(self, parser):
        parser.add_argument("csv", help="CSV file with updated page ranges")

    def handle(self, *args, **kwargs):
        self.verbosity = kwargs.get("verbosity", self.verbosity)

        # load csv file and check required fields
        excerpt_info = self.load_csv(kwargs["csv"])

        self.stats = {"error": 0, "notfound": 0, "updated": 0}

        # get script user and digwork content type for creating log entries
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        self.digwork_contentype = ContentType.objects.get_for_model(DigitizedWork)

        for row in excerpt_info:
            self.update_excerpt(row)

        self.stdout.write(
            f"\nUpdated {self.stats['updated']:,d} records. "
            + f"{self.stats['notfound']:,d} not found, "
            + f"{self.stats['error']:,d} error{'s' if self.stats['error'] != 1 else ''}."
        )

    def update_excerpt(self, row):
        """Process a row of the spreadsheet, find an existing excerpt
        by source id and original page range, and update the digital
        pages."""

        # lookup by source id and original page range
        digwork = DigitizedWork.objects.filter(
            source_id=row["source_id"], pages_orig=row["pages_orig"]
        ).first()
        if not digwork:
            self.stdout.write(
                self.style.WARNING(
                    "No record found for source id %(source_id)s and pages_orig %(pages_orig)s"
                    % row
                )
            )
            self.stats["notfound"] += 1
            return

        # update digital page range
        digwork.pages_digital = row["new_pages_digital"]
        # if this is not a change, do nothing
        if not digwork.has_changed("pages_digital"):
            return

        try:
            # save in the database;
            # should automatically recalculate page range and index page content
            digwork.save()
            self.stats["updated"] += 1
        except intspan.ParseError as err:
            self.stderr.write(
                self.style.WARNING("Error saving %s: %s" % (digwork, err))
            )
            self.stats["error"] += 1
            return

        # if changed and save succeeded, log the update
        self.log_update(digwork)

    def log_update(self, digwork):
        """Create a log entry to document digital page range change."""

        # create log entry to record what was done
        LogEntry.objects.log_action(
            user_id=self.script_user.pk,
            content_type_id=self.digwork_contentype.pk,
            object_id=digwork.pk,
            object_repr=str(digwork),
            change_message="Updated pages_digital",
            action_flag=CHANGE,
        )

    csv_required_fields = ["source_id", "pages_orig", "new_pages_digital"]

    def load_csv(self, path):
        """Load a CSV file with information about excerpts to be updated."""
        try:
            with open(path, encoding="utf-8-sig") as csvfile:
                csvreader = csv.DictReader(csvfile)
                data = [
                    row for row in csvreader if any(row.values())
                ]  # skip blank rows
        except FileNotFoundError:
            raise CommandError("Error loading the specified CSV file: %s" % path)

        csv_keys = set(data[0].keys())
        csv_key_diff = set(self.csv_required_fields).difference(csv_keys)
        # if any required fields are not present, error and quit
        if csv_key_diff:
            raise CommandError(
                "Missing required fields in CSV file: %s" % ", ".join(csv_key_diff)
            )
        return data
