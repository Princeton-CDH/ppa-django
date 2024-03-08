import csv
import os.path
import tempfile
from datetime import datetime

from django.core.management.base import BaseCommand
from django.template.defaultfilters import pluralize
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

        # generate a list of unique source ids from the queryset
        working_htids = digworks.values_list("source_id", flat=True).distinct()

        # if htids were explicitly specified, report if any are skipped
        if htids:
            skipped_htids = set(htids) - set(working_htids)
            if skipped_htids:
                self.stdout.write(
                    self.style.NOTICE(
                        f"{len(skipped_htids)} id{pluralize(skipped_htids)} "
                        + "not found in public HathiTrust volumes; "
                        + f"skipping {' '.join(skipped_htids)}"
                    )
                )

        # bail out if there's nothing to do
        # (e.g., explicit htids only and none valid)
        if not working_htids:
            self.stdout.write("No records to synchronize; stopping")
            return

        self.stdout.write(
            f"Synchronizing data for {len(working_htids)} record{pluralize(working_htids)}"
        )

        # create a tempdir for rsync logfile; will automatically be cleaned up
        output_dir = tempfile.TemporaryDirectory(prefix="ppa-rsync_")
        # we always want itemized rsync output, so we can report
        # on which htids have updated content
        htimporter = HathiImporter(
            source_ids=working_htids, rsync_output=True, output_dir=output_dir.name
        )
        logfile = htimporter.rsync_data()

        # read the rsync itemized output to identify and report on changes
        updated_files = []
        with open(logfile) as rsync_output:
            for line in rsync_output:
                # check for a line indicating that a file was updated
                if " >f" in line:
                    # rsync itemized output is white-space delimited
                    parts = line.split()
                    # last element is the filename that was updated
                    filename = parts[-1]
                    # itemized info flags precede the filename
                    flags = parts[-2]

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
                    updated_files.append(
                        {
                            "htid": htid,
                            "filename": os.path.basename(filename),
                            # rsync itemized flags look like >f.st....
                            # or >f+++++++ for new files
                            "size_changed": flags[3] == "s",
                            "modification_time": flags[4] == "t",
                            "rsync_flags": flags,
                        }
                    )

        # should this behavior only be when updating all?
        # if specific htids are specified on the command line, maybe report on them only?
        if updated_files:
            outfilename = "ppa_rsync_changes_{time}.csv".format(
                time=datetime.now().strftime("%Y%m%d-%H%M%S")
            )
            fields = updated_files[0].keys()
            print(fields)
            with open(outfilename, "w") as outfile:
                csvwriter = csv.DictWriter(outfile, fieldnames=fields)
                csvwriter.writeheader()
                csvwriter.writerows(updated_files)
            updated_htids = set([i["htid"] for i in updated_files])
            success_msg = (
                f"Updated {len(updated_files)} files for {len(updated_htids)} volumes; "
                + f"full details in {outfilename}"
            )
        else:
            success_msg = "rsync completed; no changes to report"

        self.stdout.write(self.style.SUCCESS(success_msg))
