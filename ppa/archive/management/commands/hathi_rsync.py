from django.core.management.base import BaseCommand, CommandError

from ppa.archive.import_util import HathiImporter
from ppa.archive.models import DigitizedWork


class Command(BaseCommand):
    """Update HathiTrust pairtree data via rsync"""

    help = __doc__
    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    def add_arguments(self, parser):
        parser.add_argument(
            "htids",
            nargs="*",
            help="Optional list HathiTrust ids to synchronize",
        )

    def handle(self, *args, **kwargs):
        self.verbosity = kwargs.get("verbosity", self.v_normal)
        self.options = kwargs

        # use ids specified via command line when present
        htids = kwargs.get("htids", [])

        # if hathi ids not specified via command line,
        # get all non-suppressed hathi records
        if not htids:
            htids = DigitizedWork.objects.filter(
                status=DigitizedWork.PUBLIC, source=DigitizedWork.HATHI
            ).values_list("source_id", flat=True)

        # NOTE: if htid is specified, should we verify that it's
        # in the db and not suppressed? (should import first if not)

        self.stdout.write(
            self.style.SUCCESS("Synchronizing data for %d records" % len(htids))
        )
        # even if verbosity is zero we want an output file
        htimporter = HathiImporter(
            source_ids=htids, rsync_output=self.verbosity or True
        )
        logfile = htimporter.rsync_data()
        self.stdout.write(self.style.SUCCESS("rsync output is in %s" % logfile))
