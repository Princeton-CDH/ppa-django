"""
**gale_import** is a custom manage command for bulk import of Gale
materials into the local database for management.  It takes either
a list of Gale item ids or a path to a CSV file.

Items are imported into the database for management and also indexed into
Solr as part of this import script (both works and pages).

Example usage::

    # import from a csv file
    python manage.py gale_import -c path/to/import.csv
    # import specific items
    python manage.py hathi_import galeid1 galeid2 galeid3

When using a CSV file for import, it *must* include an **ID** field;
it may also include **NOTES** (any contents will be imported into private notes),
and fields to indicate collection membership to be set on import.
These are the supported collection abbreviations:

- OB: Original Bibliography
- LIT: Literary
- MUS: Music
- TYP: Typographically Unique
- LING: Linguistic
- DIC: Dictionaries
- WL: Word Lists

"""
import csv
from collections import Counter

from django.conf import settings
from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError
from django.db.utils import IntegrityError
from django.template.defaultfilters import pluralize, truncatechars
from parasolr.django.signals import IndexableSignalHandler

from ppa.archive.gale import GaleAPI, GaleAPIError
from ppa.archive.models import Collection, DigitizedWork, Page


class Command(BaseCommand):
    """Import Gale content into PPA for management and search"""

    help = __doc__

    stats = None
    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    # input spreadsheets use the following codes as field names
    # to indicate collection membership
    collection_codes = {
        "OB": "Original Bibliography",
        "LIT": "Literary",
        "MUS": "Music",
        "TYP": "Typographically Unique",
        "LING": "Linguistic",
        "DIC": "Dictionaries",
        "WL": "Word Lists",
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "ids",
            nargs="*",
            help="Optional list of specific items to import by Gale id.",
        )
        parser.add_argument(
            "-c", "--csv", type=str, help="CSV file with items to import be imported."
        )
        # NOTE: no support for updating records for now, since Gale/ECCO records
        # will not change.

    def handle(self, *args, **kwargs):
        if not (kwargs["ids"] or kwargs["csv"]):
            raise CommandError("A list of IDs or CSV file for is required for import")

        # error handling in case user forgets to specify csv file correctly
        if 'ids' in kwargs and len(kwargs['ids']) == 1 and kwargs['ids'][0].endswith('.csv'):
            self.stdout.write(self.style.WARNING(
                '%s is not a valid id; did you forget to specify -c/--csv?' % kwargs['ids'][0]))
            return

        # NOTE: could disconnect indexing signals for more control over indexing
        # for now, leaving signal-based indexing on

        # api initialization will error if username is not in settings
        # catch and output error as command error for readability
        try:
            self.gale_api = GaleAPI()
        except ImproperlyConfigured as err:
            raise CommandError(str(err))

        self.stats = Counter()
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        self.digwork_contentype = ContentType.objects.get_for_model(DigitizedWork)

        # if ids are specified on the command line, create a list
        # of dictionaries so import will look similar to csv
        if kwargs["ids"]:
            to_import = [{"ID": gale_id} for gale_id in kwargs["ids"]]
        # when csv is specified, load rows into a list of dics
        elif kwargs["csv"]:
            to_import = self.load_csv(kwargs["csv"])
            # load collections when importing from CSV
            self.load_collections()

        # total is needed for progessbar (if we add it)
        self.stats["total"] = len(to_import)

        for item in to_import:
            if self.verbosity >= self.v_normal:
                # include title in output if present, but truncate since many are long
                self.stdout.write(
                    " ".join([item["ID"], truncatechars(item.get("Title", ""), 55)])
                )
            # send extra details to import method
            # to handle notes and collection membership from CSV
            item_info = item.copy()
            del item_info["ID"]  # don't send ID twice
            self.import_digitizedwork(item["ID"], **item_info)

        summary = (
            "\nProcessed {:,d} item{} for import."
            + "\nImported {:,d}; skipped {:,d}; {:,d} error{}; imported {:,d} page{}."
        )
        summary = summary.format(
            self.stats["total"],
            pluralize(self.stats["total"]),
            self.stats["imported"],
            self.stats["skipped"],
            self.stats["error"],
            pluralize(self.stats["error"]),
            self.stats["pages"],
            pluralize(self.stats["pages"]),
        )
        self.stdout.write(summary)

    collections = {}

    def load_collections(self):
        # load collections from the database and create
        # a lookup based on the codes used in the spreadsheet
        collections = {c.name: c for c in Collection.objects.all()}
        for code, name in self.collection_codes.items():
            self.collections[code] = collections[name]

    def load_csv(self, path):
        """Load a CSV file with items to be imported."""
        try:
            with open(path, encoding="utf-8-sig") as csvfile:
                csvreader = csv.DictReader(csvfile)
                data = [row for row in csvreader]
        except FileNotFoundError:
            raise CommandError(f"Error loading the specified CSV file: {path}")

        if "ID" not in data[0].keys():
            raise CommandError("ID column is required in CSV file")
        return data

    def import_digitizedwork(self, gale_id, **kwargs):
        """Import a single work into the database.
        Retrieves bibliographic data from Gale API."""

        # if an item with this source id exists, skip
        # (check local db first because API call is slow for large items)
        # NOTE: revisit if we decide to support update logic
        if DigitizedWork.objects.filter(source_id=gale_id).exists():
            self.stderr.write("%s is already in the database; skipping" % gale_id)
            self.stats["skipped"] += 1
            return

        try:
            item_record = self.gale_api.get_item(gale_id)
        except GaleAPIError as err:
            self.stderr.write("Error getting item information for %s" % gale_id)
            self.stats["error"] += 1
            return

        # document metadata is under "doc"
        doc_metadata = item_record["doc"]
        # NOTE: url provided in "isShownAt" includes user and source parameters;
        # these are important to preserve because it allows Gale to
        # monitor traffic source and the linked page is an "auth free" link

        # create new stub record and populate it from api response
        digwork = DigitizedWork.objects.create(
            source_id=gale_id,  # or doc_metadata['id']; format GALE|CW###
            source=DigitizedWork.GALE,
            source_url=doc_metadata["isShownAt"],
            title=doc_metadata["title"],
            # subtitle='',
            # sort_title='', # marc ?
            # authors is multivalued and not listed lastname first;
            # pull from citation? (if not from marc)
            author=", ".join(doc_metadata.get("authors", [])),
            # doc_metadata['publication']    includes title and date
            # pub_place
            # publisher
            # doc_metadata['publication']['date'] but not solely numeric
            # pub_date
            page_count=len(item_record["pageResponse"]["pages"]),
            # import any notes from csv as private notes
            notes=kwargs.get("NOTES", ""),
        )
        # set collection membership based on spreadsheet columns
        digwork_collections = [
            collection
            for code, collection in self.collections.items()
            if kwargs.get(code)
        ]
        digwork.collections.set(digwork_collections)

        # create log entry to document import
        LogEntry.objects.log_action(
            user_id=self.script_user.pk,
            content_type_id=self.digwork_contentype.pk,
            object_id=digwork.pk,
            object_repr=str(digwork),
            change_message="Created from Gale API",
            action_flag=ADDITION,
        )

        # item record used for import includes page metadata;
        # for efficiency, index pages at import time with the same api response
        DigitizedWork.index_items(
            Page.gale_page_index_data(digwork, item_record)
        )

        self.stats["imported"] += 1
        self.stats["pages"] += digwork.page_count
        return digwork
