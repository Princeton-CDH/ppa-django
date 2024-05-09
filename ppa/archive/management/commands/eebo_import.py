"""
**eebo_import** is a custom manage command for bulk import of EEBO-TCP
materials into the local database for management.  It takes a path to a
CSV file and requires that the path to EEBO data is configured
in Django settings.

Items are imported into the database for management and also indexed into
Solr as part of this import script (both works and pages).

Example usage::

    python manage.py eebo_import -c path/to/eebo_works.csv

"""

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from parasolr.django.signals import IndexableSignalHandler
import pymarc

from ppa.archive.models import Collection, DigitizedWork
from ppa.archive import eebo_tcp


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
        eebo_data_path = Path(settings.EEBO_DATA)
        if not eebo_data_path.exists():
            raise CommandError(f"EEBO_DATA directory {eebo_data_path} does not exist")

        to_import = self.load_csv(kwargs["csv"])
        # currently the CSV only specifiec OB, no other collections
        original_bibliography = Collection.objects.get(name="Original Bibliography")

        for row in to_import:
            print(row)
            source_id = eebo_tcp.short_id(row["Volume ID"])

            # create new unsaved digitized work with source type, source id
            # and any curation notes from the spreadsheet
            digwork = DigitizedWork(
                source=DigitizedWork.EEBO,
                source_id=source_id,
                source_url=row["URL"],
                notes=row["Notes"],  # TODO: confirm if we want to keep this
            )
            # populate metadata from marc record
            # path marc record
            marc_path = eebo_data_path / f"{source_id}.mrc"
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
                # TODO sort title

                # TODO: use publication info from spreadsheet or MARC?

                # confirm if this is pages digital or orig
                digwork.pages_digital = row["Sequence number"]
                # ask about pages orig
                # probably not right, but use for now to distinguish
                digwork.pages_orig = row["Section identifier"] or row["Sequence number"]

            # save the new record
            digwork.save()
            # if this record belongs to Original Bibligraphy, associate collection
            if row["OB?"] == "Y":
                digwork.collections.add(original_bibliography)

            # add log entry

        # second step for all newly imported works
        # - index pages

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
