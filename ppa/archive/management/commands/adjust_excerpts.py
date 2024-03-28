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

import logging

import intspan
from django.conf import settings
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.template.defaultfilters import pluralize

from ppa.archive.models import DigitizedWork
from ppa.archive.management.commands import hathi_excerpt

logger = logging.getLogger(__name__)


class Command(hathi_excerpt.Command):
    """Update digital page range for excerpted works."""

    help = __doc__
    # inherits csv loading & validation from hathi_excerpt command

    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal
    #: override required fields
    csv_required_fields = ["source_id", "pages_orig", "new_pages_digital"]

    def add_arguments(self, parser):
        parser.add_argument("csv", help="CSV file with updated page ranges")

    def setup(self):
        "common setup steps for running the script or testing"

        self.stats = {"error": 0, "notfound": 0, "updated": 0, "unchanged": 0}
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        self.digwork_contentype = ContentType.objects.get_for_model(DigitizedWork)

    def handle(self, *args, **kwargs):
        self.verbosity = kwargs.get("verbosity", self.verbosity)

        # load csv file and check required fields
        excerpt_info = self.load_csv(kwargs["csv"])
        self.setup()

        for row in excerpt_info:
            self.update_excerpt(row)

        # summarize what was done
        self.stdout.write(
            f"\nUpdated {self.stats['updated']:,d} "
            + f"record{pluralize(self.stats['updated'])}. "
            + f"{self.stats['unchanged']:,d} unchanged, "
            + f"{self.stats['notfound']:,d} not found, "
            + f"{self.stats['error']:,d} error{pluralize(self.stats['error'])}."
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
            self.stats["unchanged"] += 1
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
            object_repr=repr(digwork),
            change_message="Updated pages_digital",
            action_flag=CHANGE,
        )
