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
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from pairtree.pairtree_path import id_to_dirpath
from parasolr.django.signals import IndexableSignalHandler

from ppa.archive import hathi
from ppa.archive.gale import GaleAPI, GaleAPIError, MARCRecordNotFound, get_marc_record
from ppa.archive.models import DigitizedWork, Page

logger = logging.getLogger(__name__)


class DigitizedWorkImporter:
    """Logic for importing content from external sources (e.g. HathiTrust, Gale/ECCO)
    to create :class:`~ppa.archive.models.DigitizedWork`
    records. Should be extended for specific source logic.
    For use in views and manage commands."""

    existing_ids = None

    #: status - successfully imported record
    SUCCESS = 1
    #: status - skipped because already in the database
    SKIPPED = 2
    #: invalid id
    INVALID_ID = 3

    #: human-readable message to display for result status
    status_message = {
        SUCCESS: "Success",
        SKIPPED: "Skipped; already in the database",
        INVALID_ID: "Invalid id",
    }

    def __init__(self, source_ids=None):
        self.imported_works = []
        self.results = {}
        self.source_ids = source_ids or []

    def filter_existing_ids(self):
        """Check for any ids that are in the database so they can
        be skipped for import.  Populates :attr:`existing_ids`
        with an :class:`~collections.OrderedDict` of source_id -> id for
        ids already in the database and filters :attr:`source_ids`.

        :param source_ids: list of source identifiers correspending to
            :attr:`~ppa.archive.models.DigitizedWork.source_id`
        """
        # query for digitized work with these ids and return
        # source id, db id and generate an ordered dict
        self.existing_ids = OrderedDict(
            DigitizedWork.objects.filter(source_id__in=self.source_ids).values_list(
                "source_id", "id"
            )
        )

        # create initial results dict, marking any skipped ids
        self.results = OrderedDict(
            (id, self.SKIPPED) for id in self.existing_ids.keys()
        )

        # filter to ids that are not already present in the database
        self.source_ids = set(self.source_ids) - set(self.existing_ids.keys())

        # also check for and remove filter invalid ids
        self.filter_invalid_ids()

    def filter_invalid_ids(self):
        # optional filtering hook for subclasses; by default, no filtering
        # when implementing, should update self.source_ids
        pass

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
                (source_id, self.get_status_message(status))
                for source_id, status in self.results.items()
            ]
        )

    def add_item_prep(self, user=None):
        """Do any prep needed before calling :meth:`import_digitizedwork`;
        extend in subclass when needed.

        :params user: optional user to be included in log entry message
        """
        pass

    def add_items(self, log_msg_src=None, user=None):
        """Add new items from source.

        :params log_msg_src: optional source of change to be included in
            log entry message
        :params user: optional user to be included in log entry message

        """
        # assumes filter_existing_ids has already been called
        # if all ids were invalid or already present, bail out
        if not self.source_ids:
            return

        # disconnect indexing signal handler before adding new content
        IndexableSignalHandler.disconnect()
        self.add_item_prep(user=user)
        for source_id in self.source_ids:
            self.import_digitizedwork(source_id, log_msg_src, user)

        # reconnect indexing signal handler
        IndexableSignalHandler.connect()


class HathiImporter(DigitizedWorkImporter):
    """Logic for creating new :class:`~ppa.archive.models.DigitizedWork`
    records from HathiTrust. For use in views and manage commands."""

    #: rsync error
    RSYNC_ERROR = 4

    #: augment base status messages with hathi-specific codes and messages
    status_message = DigitizedWorkImporter.status_message.copy()
    status_message.update(
        {
            hathi.HathiItemNotFound: "Error loading record; check that id is valid.",
            # possibly irrelevant with removal of data api code
            hathi.HathiItemForbidden: "Permission denied to download data.",
            RSYNC_ERROR: "Failed to sync data",
            # only saw this one on day, but this was what it was
            JSONDecodeError: "HathiTrust catalog temporarily unavailable (malformed response).",
        }
    )

    def filter_invalid_ids(self):
        """Remove any ids that don't look valid. At minimum, must
        include `.` separator required for pairtree path."""
        invalid_ids = [htid for htid in self.source_ids if "." not in htid]
        # add result code to display in output
        for htid in invalid_ids:
            self.results[htid] = self.INVALID_ID
        # remove from the set of ids to be processed and return the rest
        self.source_ids = set(self.source_ids) - set(invalid_ids)

    @cached_property
    def pairtree_paths(self):
        """Dictionary of pairtree paths for each hathi id to be imported."""
        id_paths = {}
        for htid in self.source_ids:
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
        """Use rsync to retrieve data for the volumes to be imported."""

        logger.info("rsyncing pairtree data for %s", ", ".join(self.source_ids))

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

    def add_item_prep(self, user=None):
        """Prep before adding new items from HathiTrust.

        :params user: optional user to be included in log entry message

        """
        # initialize a bibliographic api client to use the same
        # session when adding multiple items
        self.bib_api = hathi.HathiBibliographicAPI()

        # use rsync to copy data from HathiTrust dataset server
        # to the local pairtree datastore for ids to be imported
        self.rsync_data()
        # FIXME: need better error handling here! rsync can error
        # or timeout; should we capture output and report that?
        # Indexing logs an error if pairtree is not present for an
        # unsuppressed work; perhaps we could do a similar check here?

    def import_digitizedwork(self, htid, log_msg_src, user):
        # if rsync did not create the expected directory,
        # set error code and bail out
        # if there is a directory but no zip file, bail out
        expected_path = os.path.join(settings.HATHI_DATA, self.pairtree_paths[htid])

        if not os.path.isdir(expected_path) or not len(
            glob.glob(os.path.join(expected_path, "*", "*.zip"))
        ):
            self.results[htid] = self.RSYNC_ERROR
            return

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


class GaleImporter(DigitizedWorkImporter):
    """Logic for creating new :class:`~ppa.archive.models.DigitizedWork`
    records from Gale/ECCO. For use in views and manage commands."""

    #: augment base status messages with hathi-specific codes and messages
    status_message = DigitizedWorkImporter.status_message.copy()
    status_message.update(
        {
            GaleAPIError: "Error getting item information from Gale API",
            MARCRecordNotFound: "MARC record not found",
        }
    )

    def add_item_prep(self, user=None):
        """Prepare for adding new items from Gale.

        :params user: optional user to be included in log entry
        """
        # disconnect indexing signal handler before adding new content
        IndexableSignalHandler.disconnect()

        # find script user if needed
        if user is None:
            self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

        self.digwork_contentype = ContentType.objects.get_for_model(DigitizedWork)
        self.gale_api = GaleAPI()

        # disconnect indexing signal handler before adding new content
        IndexableSignalHandler.disconnect()

    def add_items(self, log_msg_src=None, user=None):
        """Add new items from Gale/ECCO.

        :params log_msg_src: optional source of change to be included in
            log entry message
        :params user: optional user to be included in log entry message

        """
        # assumes filter_existing_ids has already been called
        # if all ids were invalid or already present, bail out
        if not self.source_ids:
            return

        self.add_item_prep(user=user)

        for gale_id in self.source_ids:
            self.import_digitizedwork(gale_id, log_msg_src, user)

    def import_digitizedwork(
        self, gale_id, log_msg_src="", user=None, collections=None, **kwargs
    ):
        """Import a single work into the database.
        Retrieves bibliographic data from Gale API."""
        # NOTE: significant overlap with similar method in import script

        try:
            item_record = self.gale_api.get_item(gale_id)
        except GaleAPIError as err:
            # store the error in results for reporting
            self.results[gale_id] = err
            return

        # document metadata is under "doc"
        doc_metadata = item_record["doc"]

        # create new stub record and populate it from api response
        digwork = DigitizedWork(
            source_id=gale_id,  # or doc_metadata['id']; format CW###
            source=DigitizedWork.GALE,
            # Gale API now includes ESTC id (updated June 2022)
            record_id=doc_metadata["estc"],
            source_url=doc_metadata["isShownAt"],
            # volume information should be included as volumeNumber when available
            enumcron=doc_metadata.get("volumeNumber", ""),
            title=doc_metadata["title"],
            page_count=len(item_record["pageResponse"]["pages"]),
            # import any notes from csv as private notes
            notes=kwargs.get("NOTES", ""),
            # set page range for excerpts from csv when set
            pages_digital=kwargs.get("EXCERPT PAGE RANGE", ""),
        )
        # populate titles, author, publication info from marc record
        try:
            digwork.metadata_from_marc(get_marc_record(digwork.record_id))
        except MARCRecordNotFound as err:
            # store the error in results for reporting
            self.results[gale_id] = err
            return digwork

        digwork.save()
        self.imported_works.append(digwork)

        # use user if specified, otherwise fall back to script user
        user = user or self.script_user

        # create log entry to document import
        change_message = "Created from Gale API"
        if log_msg_src:
            change_message = ("Created from Gale API %s" % log_msg_src,)
        LogEntry.objects.log_action(
            user_id=user.pk,
            content_type_id=self.digwork_contentype.pk,
            object_id=digwork.pk,
            object_repr=str(digwork),
            change_message=change_message,
            action_flag=ADDITION,
        )

        # add to list of imported works
        self.results[gale_id] = self.SUCCESS

        # set collection membership if any were specified
        if collections:
            digwork.collections.set(collections)

        # index the work once (signals index twice because of m2m change)
        DigitizedWork.index_items([digwork])

        # item record used for import includes page metadata;
        # for efficiency, index pages at import time with the same api response
        DigitizedWork.index_items(Page.gale_page_index_data(digwork, item_record))

        # return the newly created record
        return digwork

    def index(self):
        # gale records are indexed at import time, to avoid making multiple API calls
        pass
