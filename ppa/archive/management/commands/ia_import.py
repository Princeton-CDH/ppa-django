"""
**ia_import** is a custom manage command for bulk import of Internet Archive
materials into the local database for management.  It takes either a list of
IA identifiers or a path to a CSV file.

Items are imported into the database and indexed into Solr (both works and
pages) as part of this import script.

Example usage::

    # import specific items by identifier
    python manage.py ia_import gutenberg-1234 TheProdigalGuestOfHonour1905

    # import from a csv file (must contain an 'id' column)
    python manage.py ia_import -c path/to/import.csv

When using a CSV file, the following columns are recognised:

- **id** (required) — Internet Archive identifier
- **notes** — any text imported into private notes
"""
import csv
import logging
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import pluralize
from parasolr.django.signals import IndexableSignalHandler

from ppa.archive.import_util import IAImporter
from ppa.archive.internet_archive import _is_valid_ia_id
from ppa.archive.models import DigitizedWork

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Import Internet Archive content into PPA for management and search"""

    help = __doc__

    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    def add_arguments(self, parser):
        parser.add_argument(
            "ids",
            nargs="*",
            help="Optional list of specific IA identifiers to import.",
        )
        parser.add_argument(
            "-c",
            "--csv",
            type=str,
            help="CSV file with items to import (must contain an 'id' column).",
        )

    def handle(self, *args, **kwargs):
        if not (kwargs["ids"] or kwargs["csv"]):
            raise CommandError(
                "A list of IA identifiers or a CSV file is required for import"
            )

        # common mistake: pass a csv path without -c flag
        if (
            "ids" in kwargs
            and len(kwargs["ids"]) == 1
            and kwargs["ids"][0].endswith(".csv")
        ):
            self.stdout.write(
                self.style.WARNING(
                    "%s is not a valid identifier; did you forget to specify -c/--csv?"
                    % kwargs["ids"][0]
                )
            )
            return

        self.verbosity = kwargs.get("verbosity", self.v_normal)

        # disconnect signal-based indexing to avoid duplicate index calls
        IndexableSignalHandler.disconnect()

        self.stats = Counter()

        if kwargs["ids"]:
            to_import = [{"id": ia_id} for ia_id in kwargs["ids"]]
        else:
            to_import = self.load_csv(kwargs["csv"])

        self.stats["total"] = len(to_import)

        self.importer = IAImporter()
        self.importer.add_item_prep()

        for item in to_import:
            ia_id = item["id"]
            if self.verbosity >= self.v_normal:
                self.stdout.write(ia_id)
            self.import_record(ia_id, **{k: v for k, v in item.items() if k != "id"})

        summary = (
            "\nProcessed {:,d} item{}.\n"
            "Imported {:,d}; skipped {:,d}; {:,d} error{}; {:,d} invalid id{}."
        )
        self.stdout.write(
            summary.format(
                self.stats["total"],
                pluralize(self.stats["total"]),
                self.stats["imported"],
                self.stats["skipped"],
                self.stats["error"],
                pluralize(self.stats["error"]),
                self.stats["invalid"],
                pluralize(self.stats["invalid"]),
            )
        )

    def load_csv(self, path):
        """Load a CSV file and return a list of row dicts."""
        try:
            with open(path, encoding="utf-8-sig") as csvfile:
                reader = csv.DictReader(csvfile)
                data = [row for row in reader]
        except FileNotFoundError:
            raise CommandError("CSV file not found: %s" % path)

        if not data:
            raise CommandError("CSV file is empty: %s" % path)

        # accept either 'id' or 'ID' as the identifier column
        first_row = data[0]
        if "id" not in first_row and "ID" not in first_row:
            raise CommandError(
                "CSV file must contain an 'id' column (got: %s)"
                % ", ".join(first_row.keys())
            )

        # normalise column name to lowercase 'id'
        if "ID" in first_row and "id" not in first_row:
            data = [{k.lower(): v for k, v in row.items()} for row in data]

        return data

    def import_record(self, ia_id, **kwargs):
        """Import a single IA record.  Reports progress to stdout/stderr."""
        if not _is_valid_ia_id(ia_id):
            self.stderr.write(
                self.style.WARNING("Invalid IA identifier: %s — skipping" % ia_id)
            )
            self.stats["invalid"] += 1
            return

        # skip duplicates before making any API calls
        if DigitizedWork.objects.filter(
            source_id=ia_id, source=DigitizedWork.INTERNET_ARCHIVE
        ).exists():
            self.stderr.write("%s is already in the database; skipping" % ia_id)
            self.stats["skipped"] += 1
            return

        digwork = self.importer.import_digitizedwork(ia_id, **kwargs)

        result = self.importer.results.get(ia_id)

        if result == IAImporter.SUCCESS:
            self.stats["imported"] += 1
            if digwork and digwork.page_count:
                self.stats["pages"] += digwork.page_count
        elif result == IAImporter.SKIPPED:
            self.stats["skipped"] += 1
        else:
            # result is an exception instance
            self.stderr.write(
                self.style.ERROR(
                    "Error importing %s: %s" % (ia_id, result)
                )
            )
            self.stats["error"] += 1
