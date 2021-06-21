"""

Utility code related to :mod:`ppa.archives`

"""
import glob
import logging
import os
import subprocess
import tempfile
from collections import OrderedDict
from json.decoder import JSONDecodeError

from cached_property import cached_property
from django.conf import settings
from pairtree.pairtree_path import id_to_dirpath
from parasolr.django.signals import IndexableSignalHandler

from ppa.archive import hathi
from ppa.archive.models import DigitizedWork, Page


logger = logging.getLogger(__name__)


class HathiImporter:
    """Logic for creating new :class:`~ppa.archive.models.DigitizedWork`
    records from HathiTrust. For use in views and manage commands."""

    existing_ids = None

    #: status - successfully imported record
    SUCCESS = 1
    #: status - skipped because already in the database
    SKIPPED = 2
    #: rsync error
    RSYNC_ERROR = 3
    #: invalid id
    INVALID_ID = 4

    #: human-readable message to display for result status
    status_message = {
        SUCCESS: "Success",
        SKIPPED: "Skipped; already in the database",
        INVALID_ID: "Invalid id",
        hathi.HathiItemNotFound: "Error loading record; check that id is valid.",
        # possibly irrelevant with removal of data api code
        hathi.HathiItemForbidden: "Permission denied to download data.",
        RSYNC_ERROR: "Failed to sync data",
        # only saw this one on day, but this was what it was
        JSONDecodeError: "HathiTrust catalog temporarily unavailable (malformed response).",
    }

    def __init__(self, htids):
        self.imported_works = []
        self.results = {}
        self.htids = htids
        # initialize a bibliographic api client to use the same
        # session when adding multiple items
        self.bib_api = hathi.HathiBibliographicAPI()

        # not calling filter_existing_ids here because it is
        # probably not desirable behavior for current hathi_import script

    def filter_existing_ids(self):
        """Check for any ids that are in the database so they can
        be skipped for import.  Populates :attr:`existing_ids`
        with an :class:`~collections.OrderedDict` of htid -> id for
        ids already in the database and filters :attr:`htids`.

        :param htids: list of HathiTrust Identifiers (correspending to
            :attr:`~ppa.archive.models.DigitizedWork.source_id`)
        """
        # query for digitized work with these ids and return
        # source id, db id and generate an ordered dict
        self.existing_ids = OrderedDict(
            DigitizedWork.objects.filter(source_id__in=self.htids).values_list(
                "source_id", "id"
            )
        )

        # create initial results dict, marking any skipped ids
        self.results = OrderedDict(
            (htid, self.SKIPPED) for htid in self.existing_ids.keys()
        )

        # filter to ids that are not already present in the database
        self.htids = set(self.htids) - set(self.existing_ids.keys())

        # also check for and remove filter invalid ids
        self.filter_invalid_ids()

    def filter_invalid_ids(self):
        # remove any ids that don't look valid
        # at minimum, must have . separator required for pairtree path
        invalid_ids = [htid for htid in self.htids if "." not in htid]
        # add result code to display in output
        for htid in invalid_ids:
            self.results[htid] = self.INVALID_ID
        # remove from the set of ids to be processed
        self.htids = set(self.htids) - set(invalid_ids)

    @cached_property
    def pairtree_paths(self):
        """Dictionary of pairtree paths for each hathi id to be imported."""
        id_paths = {}
        for htid in self.htids:
            # split institional prefix from identifier
            prefix, ident = htid.split(".", 1)
            # generate pairtree path for the item
            id_paths[htid] = os.path.join(prefix, "pairtree_root", id_to_dirpath(ident))
            # ensure pairtree prefix and version files are included
            # for each prefix, so new prefixes will result in valid pairtrees
            id_paths[prefix] = "%s/pairtree_prefix" % prefix
            # wildcard doesn't work here; if hathitrust ever changes pairtree
            # version, this will likely need to change!
            id_paths["%s_version" % prefix] = "%s/pairtree_version0_1" % prefix
        return id_paths

    # rsync command adapted from HathiTrust dataset sync documentation:
    # https://github.com/hathitrust/datasets/wiki/Dataset-rsync-instructions
    # recursive, copy links, preserve times, delete extra files at destination
    # NOTE: add -v if needed for debugging
    rsync_cmd = (
        "rsync -rLt --delete --ignore-errors "
        + " --files-from=%(path_file)s %(server)s:%(src)s %(dest)s"
    )

    RSYNC_RETURN_CODES = {
        1: "Syntax or usage error",
        2: "Protocol incompatibility",
        3: "Errors selecting input/output files, dirs",
        4: "Requested action not supported",
        # ... : an attempt was made to manipulate 64-bit
        # files on a platform that cannot support them; or an option was specified
        # that is supported by the client and not by the server.
        5: "Error starting client-server protocol",
        6: "Daemon unable to append to log-file",
        10: "Error in socket I/O",
        11: "Error in file I/O",
        12: "Error in rsync protocol data stream",
        13: "Errors with program diagnostics",
        14: "Error in IPC code",
        20: "Received SIGUSR1 or SIGINT",
        21: "Some error returned by waitpid()",
        22: "Error allocating core memory buffers",
        23: "Partial transfer due to error",
        24: "Partial transfer due to vanished source files",
        25: "The --max-delete limit stopped deletions",
        30: "Timeout in data send/receive",
        35: "Timeout waiting for daemon connection",
    }

    def rsync_data(self):
        # create temp file with list of paths to synchronize
        with tempfile.NamedTemporaryFile(
            prefix="ppa_hathi_pathlist-", suffix=".txt", mode="w+t"
        ) as fp:

            file_paths = list(self.pairtree_paths.values())
            # sorting makes rsync more efficient
            file_paths.sort()
            fp.write("\n".join(file_paths))

            # flush to make content available to rsync
            fp.flush()

            # populate rsync command with path file name,
            # local hathi data dir, and remote dataset server and source
            rsync_cmd = self.rsync_cmd % {
                "path_file": fp.name,
                "server": settings.HATHITRUST_RSYNC_SERVER,
                "src": settings.HATHITRUST_RSYNC_PATH,
                "dest": settings.HATHI_DATA,
            }
            logger.debug("rsync command: %s" % rsync_cmd)
            try:
                subprocess.run(args=rsync_cmd.split(), check=True)
            except subprocess.CalledProcessError as err:
                logger.error(
                    "HathiTrust rsync failed — %s / command: %s"
                    % (self.RSYNC_RETURN_CODES[err.returncode], rsync_cmd)
                )

    def add_items(self, log_msg_src=None, user=None):
        """Add new items from HathiTrust.

        :params log_msg_src: optional source of change to be included in
            log entry message

        """

        # if all ids were invalid or already present, bail out
        if not self.htids:
            return

        # disconnect indexing signal handler before adding new content
        IndexableSignalHandler.disconnect()

        # use rsync to copy data from HathiTrust dataset server
        # to the local pairtree datastore for ids to be imported
        logger.info("rsyncing pairtree data for %s", ", ".join(self.htids))
        self.rsync_data()
        # FIXME: need better error handling here! rsync can error
        # or timeout; should we capture output and report that?
        # Indexing logs an error if pairtree is not present for an
        # unsuppressed work; perhaps we could do a similar check here?

        for htid in self.htids:
            # if rsync did not create the expected directory,
            # set error code and bail out
            # if there is a directory but no zip file, bail out
            expected_path = os.path.join(settings.HATHI_DATA, self.pairtree_paths[htid])

            if not os.path.isdir(expected_path) or not len(
                glob.glob(os.path.join(expected_path, "*", "*.zip"))
            ):
                self.results[htid] = self.RSYNC_ERROR
                continue

            try:
                # fetch metadata and add to the database
                digwork = DigitizedWork.add_from_hathi(
                    htid, self.bib_api, log_msg_src=log_msg_src, user=user
                )
                if digwork:
                    # populate page count
                    digwork.count_pages()
                    self.imported_works.append(digwork)

                self.results[htid] = self.SUCCESS
            except (
                hathi.HathiItemNotFound,
                JSONDecodeError,
                hathi.HathiItemForbidden,
            ) as err:
                # json decode error occurred 3/26/2019 - catalog was broken
                # and gave a 200 Ok response with PHP error content
                # hopefully temporary, but could occur again...

                # store the actual error as the results, so that
                # downstream code can report as desired
                self.results[htid] = err

                # remove the partial record if one was created
                # (i.e. if metadata succeeded but data failed)
                DigitizedWork.objects.filter(source_id=htid).delete()

        # reconnect indexing signal handler
        IndexableSignalHandler.connect()

    def index(self):
        """Index newly imported content, both metadata and full text."""
        if self.imported_works:
            DigitizedWork.index_items(self.imported_works)
            for work in self.imported_works:
                # index page index data in chunks (returns a generator)
                DigitizedWork.index_items(Page.page_index_data(work))

    def get_status_message(self, status):
        """Get a readable status message for a given status"""
        try:
            # try message for simple states (success, skipped)
            return self.status_message[status]
        except KeyError:
            # if that fails, check for error message
            return self.status_message[status.__class__]

    def output_results(self):
        """Provide human-readable report of results for each
        id that was processed."""
        return OrderedDict(
            [
                (htid, self.get_status_message(status))
                for htid, status in self.results.items()
            ]
        )
