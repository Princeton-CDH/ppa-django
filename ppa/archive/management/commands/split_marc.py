from collections import Counter
from io import StringIO, BytesIO

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import pluralize
import pymarc

from ppa.archive.gale import get_marc_storage


class Command(BaseCommand):
    """Split MARC records out so they are easily accessible by item id
    for import and Zotero metadata."""

    help = __doc__

    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    def add_arguments(self, parser):
        parser.add_argument(
            "marcfiles", nargs="+", help="List of MARC files to read and split"
        )

    def handle(self, *args, **kwargs):
        # initialize pairtree storage for storing the split out
        # marc files
        marc_store = get_marc_storage()
        stats = Counter()
        for filepath in kwargs["marcfiles"]:
            stats["files"] += 1
            with open(filepath, "rb") as marcfile:
                reader = pymarc.MARCReader(marcfile, to_unicode=True)
                for record in reader:
                    # Gale item id used for API is only available in the
                    # access url; split the url and get the id
                    gale_id = record["856"]["u"].split("/")[5]
                    # create an object in the pairtree
                    pmarc = marc_store.get_object(gale_id, create_if_doesnt_exist=True)
                    # add individual binary marc record to pairtree storage
                    output = BytesIO()
                    record.force_utf8 = True
                    output.write(record.as_marc())
                    pmarc.add_bytestream("marc.dat", output.getvalue())
                    stats["records"] += 1

        self.stdout.write(
            "Split out %d record%s from %s file%s"
            % (
                stats["records"],
                pluralize(stats["records"]),
                stats["files"],
                pluralize(stats["files"]),
            )
        )
