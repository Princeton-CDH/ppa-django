import csv
from collections import Counter

import intspan
from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from parasolr.django.signals import IndexableSignalHandler

from ppa.archive.models import Collection, DigitizedWork


class Command(BaseCommand):
    """Convert existing HathiTrust full works into excerpts"""

    help = __doc__

    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    # item type lookup for supported types
    item_type = {"Excerpt": DigitizedWork.EXCERPT, "Article": DigitizedWork.ARTICLE}

    def add_arguments(self, parser):
        parser.add_argument("csv", help="CSV file with excerpt information")

    def setup(self):
        # common setup steps for running the script or testing
        self.stats = Counter()
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        self.digwork_contentype = ContentType.objects.get_for_model(DigitizedWork)
        # load collections from the database
        self.load_collections()

    def handle(self, *args, **kwargs):
        # disconnect signal handler so indexing can be controlled
        IndexableSignalHandler.disconnect()

        self.verbosity = kwargs.get("verbosity", self.v_normal)

        # load csv file and check required fields
        excerpt_info = self.load_csv(kwargs["csv"])

        self.setup()
        for row in excerpt_info:
            self.excerpt(row)

        self.stdout.write(
            "\nExcerpted {excerpted:,d} existing records; created {created:,d} new excerpts. {error:,d} errors.".format_map(
                self.stats
            )
        )

    def load_collections(self):
        """load collections from the database and create a lookup
        based on collection names"""
        self.collections = {c.name: c for c in Collection.objects.all()}

    def excerpt(self, row):
        """Process a row of the spreadsheet, and either convert an existing full
        work to an excerpt or create a new excerpt."""

        # volume id in spreadsheet is our source id
        source_id = row["Volume ID"]
        # by default, assume we're modifying an existing record
        created = False
        # first look for an existing full work to convert to excerpt
        digwork = DigitizedWork.objects.filter(
            source_id=source_id,
            item_type=DigitizedWork.FULL,
            source=DigitizedWork.HATHI,
        ).first()

        # if there is no existing work to convert, create a new one
        if not digwork:
            digwork = DigitizedWork(source_id=source_id, source=DigitizedWork.HATHI)
            # set created flag to true
            created = True

        # update all fields from spreadsheet data
        # - required fields
        digwork.item_type = self.item_type[row["Item Type"]]
        digwork.title = row["Title"]
        digwork.sort_title = row["Sort Title"]
        digwork.book_journal = row["Book/Journal Title"]
        # intspan requires commas; allow semicolons in input but convert to commas
        digwork.pages_digital = row["Digital Page Range"].replace(";", ",")
        digwork.record_id = row["Record ID"]
        # - optional fields
        digwork.author = row.get("Author", "")
        digwork.pub_date = (
            row.get("Publication Date", "") or None
        )  # numeric, not string
        digwork.pub_place = row.get("Publication Place", "")
        digwork.publisher = row.get("Publisher", "")
        digwork.enumcron = row.get("Enumcron", "")
        digwork.pages_orig = row.get("Original Page Range", "")

        digwork.notes = row.get("Notes", "")
        digwork.public_notes = row.get("Public Notes", "")

        # save to create or update
        try:
            digwork.save()
        except intspan.ParseError as err:
            self.stderr.write(
                self.style.WARNING("Error saving %s: %s" % (source_id, err))
            )
            self.stats["error"] += 1
            return

        # set collection membership based on spreadsheet data:
        # collection is a single field with collection names delimited by semicolon
        if row["Collection"]:
            digwork_collections = [
                self.collections[coll] for coll in row["Collection"].split(";")
            ]
            if digwork_collections:
                digwork.collections.set(digwork_collections)

        self.log_action(digwork, created)

        if created:
            self.stats["created"] += 1
        else:
            self.stats["excerpted"] += 1

        # Pages are automatically indexed due to page range check in save method.
        # Index the new or updated work in solr
        DigitizedWork.index_items([digwork])

    def log_action(self, digwork, created=True):
        """Create a log entry to document excerpting or creating the record.
        Message and action flag are determined by created boolean."""
        if created:
            log_message = "Created via hathi_excerpt script"
            log_action = ADDITION
        else:
            log_message = "Converted to excerpt"
            log_action = CHANGE

        # create log entry to record what was done
        LogEntry.objects.log_action(
            user_id=self.script_user.pk,
            content_type_id=self.digwork_contentype.pk,
            object_id=digwork.pk,
            object_repr=str(digwork),
            change_message=log_message,
            action_flag=log_action,
        )

    csv_required_fields = [
        "Item Type",
        "Volume ID",
        "Title",
        "Sort Title",
        "Book/Journal Title",
        "Digital Page Range",
        "Collection",
        "Record ID",
    ]
    # supported but not required:
    # Author, Publication Date, Publication Place, Publisher, Enumcron, Original Page Range,
    # Notes, Public Notes,

    def load_csv(self, path):
        """Load a CSV file with digworks to be excerpted."""
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
