from collections import Counter
from io import BytesIO, StringIO

import pymarc
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import pluralize

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
                reader = pymarc.MARCReader(
                    marcfile, to_unicode=True, utf8_handling="replace"
                )
                for record in reader:
                    # use ESTC id from 001 as identifier
                    # (need a mapping from Gale item id to ESTC; only
                    # one marc record for each volume in a multivolume set)
                    gale_estc_id = record["001"].value().strip()
                    # create an object in the pairtree
                    pmarc = marc_store.get_object(
                        gale_estc_id, create_if_doesnt_exist=True
                    )
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
