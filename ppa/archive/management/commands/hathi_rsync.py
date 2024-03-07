import os.path
from datetime import datetime

from django.core.management.base import BaseCommand
from pairtree import path2id

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

        # by default, sync data for all non-suppressed hathi source ids
        digworks = DigitizedWork.objects.filter(
            status=DigitizedWork.PUBLIC, source=DigitizedWork.HATHI
        )

        # if htids are specified via parameter, use them to filter
        # the queryset, to ensure we only sync records that are
        # in the database and not suppressed
        if htids:
            digworks = digworks.filter(source_id__in=htids)
        # NOTE: report here on any skipped ids?

        # generate a list of unique source ids from the queryset
        hathi_ids = digworks.values_list("source_id", flat=True).distinct()
        self.stdout.write("Synchronizing data for %d records" % len(hathi_ids))
        # we always want itemized rsync output, so we can report
        # on which volumes were updated
        htimporter = HathiImporter(
            source_ids=hathi_ids, rsync_output=True, output_dir="/tmp"
        )
        logfile = htimporter.rsync_data()

        # read the rsync itemized output to identify records where file
        # sizes changed
        updated_ids = set()
        with open(logfile) as rsync_output:
            for line in rsync_output:
                # if a line indicates that a file was updated due
                # to a change in size, use the path to determine the hathi id
                if " >f.s" in line:
                    # rsync itemized output is white-space delimited;
                    # last element is the filename that was updated
                    filename = line.rsplit()[-1].strip()
                    # we only care about zip files and mets.xml files
                    if not filename.endswith(".zip") and not filename.endswith(".xml"):
                        continue
                    # reconstruct the hathi id from the filepath
                    ht_prefix, pairtree_dir = filename.split("/pairtree_root/", 1)
                    # get the directory one level up from the updated file
                    pairtree_id = os.path.dirname(os.path.dirname(pairtree_dir))
                    # use pairtree to determine the id based on the path
                    # (handles special characters like those used in ARKs)
                    htid = f"{ht_prefix}.{path2id(pairtree_id)}"
                    updated_ids.add(htid)

        # should this behavior only be when updating all?
        # if specific htids are specified on the command line, maybe report on them only?
        if updated_ids:
            outfilename = "ppa_rsync_updated_htids_%s.txt" % datetime.now().strftime(
                "%Y%m%d-%H%M%S"
            )
            with open(outfilename, "w") as outfile:
                outfile.write("\n".join(sorted(updated_ids)))
            success_msg = (
                f"File sizes changed for {len(updated_ids)} hathi ids; "
                + f"full list in {outfilename}"
            )
        else:
            success_msg = "rsync completed; no changes to report"

        self.stdout.write(self.style.SUCCESS(success_msg))
