"""
**eebo_import** is a custom manage command for bulk import of EEBO-TCP
materials into the local database for management.  It takes a path to a
CSV file and requires that the path to EEBO data is configured
in Django settings.

Items are imported into the database for management and also indexed into
Solr as part of this import script (both works and pages).

Example usage::

    python manage.py eebo_import path/to/eebo_works.csv

"""

import csv
from pathlib import Path

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from parasolr.django.signals import IndexableSignalHandler
import pymarc

from ppa.archive import eebo_tcp
from ppa.archive.models import Collection, DigitizedWork


class Command(BaseCommand):
    """Import EEBO-TCP content into PPA for management and search"""

    help = __doc__
    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    def add_arguments(self, parser):
        parser.add_argument(
            "csv", type=str, help="CSV file with EEBO-TCP items to import."
        )

    def handle(self, *args, **kwargs):
        self.verbosity = kwargs.get("verbosity", self.v_normal)

        # disconnect signal-based indexing and bulk-index after import
        IndexableSignalHandler.disconnect()

        # make sure eebo data path is configured in django settings
        if not getattr(settings, "EEBO_DATA", None):
            raise CommandError(
                "Path for EEBO_DATA must be configured in Django settings"
            )
        self.eebo_data_path = Path(settings.EEBO_DATA)
        if not self.eebo_data_path.exists():
            raise CommandError(
                f"EEBO_DATA directory {self.eebo_data_path} does not exist"
            )

        to_import = self.load_csv(kwargs["csv"])
        # currently the CSV only specifiec OB, no other collections
        original_bibliography = Collection.objects.get(name="Original Bibliography")

        # get script user and content type for creating log entries
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        self.digwork_contentype = ContentType.objects.get_for_model(DigitizedWork)

        imported_works = []

        for row in to_import:
            digwork = self.create_eebo_digwork(row)
            # if this record belongs to Original Bibligraphy, associate collection
            if row["OB?"] == "Y":
                digwork.collections.add(original_bibliography)

            # create log entry to document db record creation
            LogEntry.objects.log_action(
                user_id=self.script_user.pk,
                content_type_id=self.digwork_contentype.pk,
                object_id=digwork.pk,
                object_repr=str(digwork),
                change_message="Created via eebo_import manage command",
                action_flag=ADDITION,
            )
            # add to list
            imported_works.append(digwork)

        # index all imported works in Solr
        DigitizedWork.index_items(imported_works)
        # then index all the pages for non-excerpt works
        # (excerpt pages are indexed automatically on save)
        # using index_pages command because it has been optimized
        full_work_ids = [
            digwork.source_id
            for digwork in imported_works
            if digwork.item_type == DigitizedWork.FULL
        ]
        if full_work_ids:
            # calling index_pages command doesn't work from here;
            # just tell the user what command to run
            self.stdout.write("Now index pages for the full works with this command:")
            self.stdout.write(f"python manage.py index_pages {' '.join(full_work_ids)}")

    def create_eebo_digwork(self, row):
        source_id = eebo_tcp.short_id(row["Volume ID"])
        # NOTE: for simplicity, this is written as a a one-time import.
        # for development, use admin filter by source to delete and re-import

        # create new unsaved digitized work with source type, source id
        # and any curation notes from the spreadsheet
        digwork = DigitizedWork(
            source=DigitizedWork.EEBO,
            source_id=source_id,
            source_url=row["URL"],
            notes=row["Notes"],  # curation notes (not public notes)
        )
        # populate metadata from marc record
        # path marc record
        marc_path = self.eebo_data_path / f"{source_id}.mrc"
        with marc_path.open("rb") as marc_filehandle:
            marc_reader = pymarc.MARCReader(marc_filehandle)
            # get the first record (file contains one one record only)
            marc_record = next(marc_reader)
            digwork.metadata_from_marc(marc_record, populate=True)

        # if this is an excerpt, set item type, page range, and
        # override metadata from the spreadsheet
        if row["Excerpt? Y/N"] == "Y":
            digwork.item_type = DigitizedWork.EXCERPT
            digwork.author = row["Author"]
            digwork.title = row["Title"]
            # clear out any subtitle set from MARC record
            digwork.subtitle = ""
            # sort title and book/journal title must be set manually for excerpts
            digwork.sort_title = row["Sort Titles (EXCERPT ONLY)"]
            digwork.book_journal = row["Book/journal title (EXCERPT ONLY)"]
            # for all other fields, we use publication info from MARC

            # digital page range in spreadsheet
            digwork.pages_digital = row["Sequence number"]
            # original page range in spreadsheet
            digwork.pages_orig = row["Original page range"]

        else:
            # for non-excerpts, calculate number of pages
            digwork.page_count = eebo_tcp.page_count(digwork.source_id)

        # save the new record
        digwork.save()

        return digwork

    def load_csv(self, path):
        """Load a CSV file with items to be imported."""
        # adapted from gale import script
        try:
            with open(path, encoding="utf-8-sig") as csvfile:
                csvreader = csv.DictReader(csvfile)
                data = [row for row in csvreader]
        except FileNotFoundError:
            raise CommandError("Error loading the specified CSV file: %s" % path)

        if "Volume ID" not in data[0].keys():
            raise CommandError("Volume ID column is required in CSV file")
        return data
