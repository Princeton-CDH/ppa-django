"""
**hathi_import** is a custom manage command for bulk import of HathiTrust
materials into the local database for management.  It does *not* index
into Solr for search and browse; use the **index** script for that after
import.

This script expects a local copy of dataset files in pairtree format
retrieved by rsync.  (Note that pairtree data must include pairtree
version file to be valid.)

Contents are inspected from the configured **HATHI_DATA** path;
:class:`~ppa.archive.models.DigitizedWork` records are created or updated
based on identifiers found and metadata retrieved from the HathiTrust
Bibliographic API.  Page content is only reflected in the database
via a total page count per work (but page contents will be indexed in
Solr via **index** script).

By default, existing records are updated only when the Hathi record has changed
or if requested via `--update`` script option.

Supports importing specific items by hathi id, but the pairtree content
for the items still must exist at the configured path.

Example usage::

    # import everything with defaults
    python manage.py hathi_import
    # import specific items
    python manage.py hathi_import htid1 htid2 htid3
    # re-import and update records
    python manage.py hathi_import --update
    # display progressbar to show status and ETA
    python manage.py hathi_import -v 0 --progress

"""


from collections import defaultdict
from glob import glob
import logging
import os
import time

from django.conf import settings
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import pluralize
from django.utils.timezone import now
from pairtree import pairtree_client, storage_exceptions
from parasolr.django.signals import IndexableSignalHandler
import progressbar

from ppa.archive.hathi import HathiBibliographicAPI, HathiItemNotFound
from ppa.archive.models import DigitizedWork


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Import HathiTrust digitized items into PPA to be managed and searched"""

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
            "htids",
            nargs="*",
            help="Optional list of specific volumes to import by HathiTrust id.",
        )
        parser.add_argument(
            "-u",
            "--update",
            action="store_true",
            help="Update local content even if source record has not changed.",
        )
        parser.add_argument(
            "--progress",
            action="store_true",
            help="Display a progress bar to track the status of the import.",
        )

    def handle(self, *args, **kwargs):
        # disconnect signal handler for on-demand indexing, for efficiency
        # (index in bulk after an update, not one at a time)
        IndexableSignalHandler.disconnect()

        self.bib_api = HathiBibliographicAPI()
        self.verbosity = kwargs.get("verbosity", self.v_normal)
        self.options = kwargs
        self.digwork_content_type = ContentType.objects.get_for_model(DigitizedWork)

        # bulk import only for now
        # - eventually support list of ids + rsync?

        # for now, start with existing rsync data
        # - get list of ids, rsync data, grab metadata
        # - populate database only (does not index in solr); if a work
        #   has already been imported, will only update if changed in hathi
        #   or update requested in script options

        self.stats = defaultdict(int)

        # if ids are explicitly specified on the command line, only
        # index those items
        # (currently still requires rsync data to be present on the filesystem)
        if self.options["htids"]:
            ids_to_import = self.options["htids"]
            self.stats["total"] = len(ids_to_import)
        else:
            # otherwise, find and import everything in the pairtree data
            ids_to_import = self.get_hathi_ids()
            self.stats["total"] = self.count_hathi_ids()

        if self.options["progress"]:
            progbar = progressbar.ProgressBar(
                redirect_stdout=True, max_value=self.stats["total"]
            )
        else:
            progbar = None

        # initialize access to rsync data as dict of pairtrees by prefix
        self.initialize_pairtrees()

        for htid in ids_to_import:
            if self.verbosity >= self.v_normal:
                self.stdout.write(htid)
            self.stats["count"] += 1

            digwork = self.import_digitizedwork(htid)
            # if no item is returned, either there is an error or no update
            # is needed; update count and go to the next item
            if not digwork:
                if progbar:
                    progbar.update(self.stats["count"])
                continue

            # count pages in the pairtree zip file and update digwork page count
            try:
                self.stats["pages"] += digwork.count_pages()
            except storage_exceptions.ObjectNotFoundException:
                self.stderr.write("%s not found in datastore" % digwork.source_id)

            if progbar:
                progbar.update(self.stats["count"])

        summary = (
            "\nProcessed {:,d} item{} for import."
            + "\nAdded {:,d}; updated {:,d}; skipped {:,d}; {:,d} error{}; imported {:,d} page{}."
        )
        summary = summary.format(
            self.stats["total"],
            pluralize(self.stats["total"]),
            self.stats["created"],
            self.stats["updated"],
            self.stats["skipped"],
            self.stats["error"],
            pluralize(self.stats["error"]),
            self.stats["pages"],
            pluralize(self.stats["pages"]),
        )
        self.stdout.write(summary)

    def initialize_pairtrees(self):
        """Initiaulize pairtree storage clients for each
        subdirectory in the configured **HATHI_DATA** path."""

        # if the configured directory does not exist or is not
        # a directory, bail out
        if not os.path.isdir(settings.HATHI_DATA):
            raise CommandError(
                "Configuration error for HATHI_DATA dir (%s)" % settings.HATHI_DATA
            )

        # HathiTrust data is constructed with instutition short name
        # with pairtree root underneath each
        if not self.hathi_pairtree:
            hathi_dirs = glob(os.path.join(settings.HATHI_DATA, "*"))
            for ht_data_dir in hathi_dirs:
                prefix = os.path.basename(ht_data_dir)

                hathi_ptree = pairtree_client.PairtreeStorageClient(prefix, ht_data_dir)
                # store initialized pairtree client by prefix for later use
                self.hathi_pairtree[prefix] = hathi_ptree

    def get_hathi_ids(self):
        """Generator of hathi ids from previously rsynced hathitrust data,
        based on the configured **HATHI_DATA** path in settings."""

        self.initialize_pairtrees()
        for prefix, hathi_ptree in self.hathi_pairtree.items():
            for hathi_id in hathi_ptree.list_ids():
                # NOTE: prefix should automatially be handled based on
                # pairtree_prefix, but python pairtree library doesn't
                # yet include logic for that
                yield "%s.%s" % (prefix, hathi_id)

    def count_hathi_ids(self):
        """count items in the pairtree structure without loading
        all into memory at once."""
        start = time.time()
        count = sum(1 for i in self.get_hathi_ids())
        logger.debug("Counted hathi ids in %f sec" % (time.time() - start))
        return count

    def import_digitizedwork(self, htid):
        """Import a single work into the database.
        Retrieves bibliographic data from Hathi api. If the record already
        exists in the database, it is only updated if the hathi record
        has changed or if an update is requested by the user.
        Creates admin log entry for record creation or record update.
        Returns None if there is an error retrieving bibliographic data
        or no update is needed; otherwise, returns the
        :class:`~ppa.archive.models.DigitizedWork`."""

        # store the current time to find log entries created after
        before = now()

        try:
            digwork = DigitizedWork.add_from_hathi(
                htid,
                self.bib_api,
                update=self.options["update"],
                log_msg_src="via hathi_import script",
            )
        except HathiItemNotFound:
            self.stdout.write("Error: Bibliographic data not found for '%s'" % htid)
            self.stats["error"] += 1
            return

        # check log entries for this record to determine what was done
        log_entries = LogEntry.objects.filter(
            content_type_id=self.digwork_content_type.pk,
            object_id=digwork.pk,
            action_time__gte=before,
        )

        # no log entry - nothing was done (not new, no update needed)
        if not log_entries.exists():
            # local copy is newer than last source modification date
            if self.verbosity > self.v_normal:
                self.stdout.write(
                    "Source record last updated %s, no update needed"
                    % digwork.updated.date()
                )
            # nothing to do; continue to next item
            self.stats["skipped"] += 1

        elif log_entries.first().action_flag == CHANGE:
            # report if record was changed and update not forced
            if not self.options["update"]:
                self.stdout.write(
                    "Source record last updated %s, update needed"
                    % digwork.updated.date()
                )
            # count the update
            self.stats["updated"] += 1

        elif log_entries.first().action_flag == ADDITION:
            # count the new record
            self.stats["created"] += 1

        return digwork
