"""
**gale_import** is a custom manage command for bulk import of Gale
materials into the local database for management.


"""
import csv
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import pluralize, truncatechars
from parasolr.django.signals import IndexableSignalHandler

from ppa.archive.gale import GaleAPI, GaleAPIError
from ppa.archive.models import DigitizedWork


class Command(BaseCommand):
    """Import Gale content into PPA for management and search"""

    help = __doc__

    bib_api = None
    hathi_pairtree = {}
    stats = None
    options = {}
    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    def add_arguments(self, parser):
        parser.add_argument(
            "ids",
            nargs="*",
            help="Optional list of specific items to import by Gale id.",
        )
        parser.add_argument(
            "--csv", type=str, help="CSV file with items to import be imported."
        )

        # TODO: require one and only one of ids or csv argument

        # parser.add_argument(
        #     '-u', '--update', action='store_true',
        #     help='Update local content even if source record has not changed.')
        # parser.add_argument(
        #     '--progress', action='store_true',
        #     help='Display a progress bar to track the status of the import.')

    def handle(self, *args, **kwargs):
        # disconnect signal handler for on-demand indexing, for efficiency
        # (index in bulk after an update, not one at a time)
        IndexableSignalHandler.disconnect()

        self.gale_api = GaleAPI()
        self.stats = Counter()

        # if ids are specified on the command line, create a list
        # of dictionaries so import will look similar to csv
        if kwargs["ids"]:
            to_import = [{"ID": gale_id} for gale_id in kwargs["ids"]]
        # when csv is specified, load rows into a list of dics
        elif kwargs["csv"]:
            to_import = self.load_csv(kwargs["csv"])
        else:
            raise CommandError("Must specify items to import by id or CSV file")

        # needed for progessbar
        self.stats["total"] = len(to_import)

        for item in to_import:
            if self.verbosity >= self.v_normal:
                # include title in output if present, but truncate since many are long
                self.stdout.write(' '.join([item["ID"], truncatechars(item.get("Title", ''), 55)]))
            self.import_digitizedwork(item["ID"], **item)

        summary = (
            "\nProcessed {:,d} item{} for import."
            + "\nImported {:,d}; {:,d} error{}; imported {:,d} page{}."
        )
        summary = summary.format(
            self.stats["total"],
            pluralize(self.stats["total"]),
            self.stats["imported"],
            self.stats["error"],
            pluralize(self.stats["error"]),
            self.stats["pages"],
            pluralize(self.stats["pages"]),
        )
        self.stdout.write(summary)

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

        try:
            item_record = self.gale_api.get_item(gale_id)
        except GaleAPIError as err:
            self.stderr.write("Error loading item : %s" % gale_id)
            self.stats["error"] += 1
            return

        # document metadata is under
        doc_metadata = item_record["doc"]
        # gale url includes user and source parameters (sid=gale_api),
        # but we don't want to keep them
        gale_url = doc_metadata["isShownAt"].split("?", 1)[0]

        # create new stub record and populate it from api response
        digwork = DigitizedWork.objects.create(
            source_id=gale_id,  # or doc_metadata['id']; format GALE|CW###
            source=DigitizedWork.GALE,
            source_url=gale_url,
            title=doc_metadata["title"],
            # subtitle='',
            # sort_title='', # marc ?
            # authors is multivalued and not listed lastname first;
            # pull from citation? (if not from marc)
            author=", ".join(doc_metadata["authors"]),
            # doc_metadata['publication']    includes title and date
            # pub_place
            # publisher
            # doc_metadata['publication']['date'] but not solely numeric
            # pub_date
            page_count=len(item_record["pageResponse"]["pages"]),
            # store citation in notes for now; include any notes from csv
            notes="\n".join(
                [n for n in (kwargs.get("NOTES"), doc_metadata["citation"]) if n]
            ),
        )

        # try:
        #     digwork = DigitizedWork.add_from_hathi(
        #         htid, self.bib_api, update=self.options['update'],
        #         log_msg_src='via hathi_import script')
        # except HathiItemNotFound:
        #     self.stdout.write("Error: Bibliographic data not found for '%s'" % htid)
        #     self.stats['error'] += 1
        #     return

        # TODO: create log entry to document import

        # NOTE: item record includes page metadata; we should index
        # at the same time as import

        self.stats["imported"] += 1
        self.stats["pages"] += digwork.page_count
        return digwork
