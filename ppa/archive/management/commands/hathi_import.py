'''
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

'''


from collections import defaultdict
from glob import glob
import logging
import os
import time
from zipfile import ZipFile

from django.conf import settings
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.template.defaultfilters import pluralize
from pairtree import pairtree_path, pairtree_client
import progressbar

from ppa.archive.hathi import HathiBibliographicAPI, HathiItemNotFound
from ppa.archive.models import DigitizedWork
from ppa.archive.management.commands.retry import Retry


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    '''Import HathiTrust digitized items into PPA to be managed and searched'''
    help = __doc__

    bib_api = None
    hathi_pairtree = {}
    stats = None
    script_user = None
    options = {}
    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    def add_arguments(self, parser):
        parser.add_argument('htids', nargs='*',
            help='Optional list of specific volumes to index by HathiTrust id.')
        parser.add_argument('-u', '--update', action='store_true',
            help='Update local content even if source record has not changed.')
        parser.add_argument('--progress', action='store_true',
            help='Display a progress bar to track the status of the import.')

    @Retry(ConnectionError)
    def handle(self, *args, **kwargs):
        self.bib_api = HathiBibliographicAPI()
        self.verbosity = kwargs.get('verbosity', self.v_normal)
        self.options = kwargs

        # bulk import only for now
        # - eventually support list of ids + rsync?

        # for now, start with existing rsync data
        # - get list of ids, rsync data, grab metadata
        # - populate database only (does not index in solr); if a work
        #   has already been imported, will only update if changed in hathi
        #   or update requested in script options

        self.stats = defaultdict(int)

        # retrieve script user for generating log entries / record history
        self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

        # if ids are explicitly specified on the command line, only
        # index those items
        # (currently still requires rsync data to be present on the filesystem)
        if self.options['htids']:
            ids_to_index = self.options['htids']
            self.stats['total'] = len(ids_to_index)
        else:
            # otherwise, find and index everything in the pairtree data
            ids_to_index = self.get_hathi_ids()
            self.stats['total'] = self.count_hathi_ids()

        if self.options['progress']:
            progbar = progressbar.ProgressBar(redirect_stdout=True,
                                              max_value=self.stats['total'])
        else:
            progbar = None

        # initialize access to rsync data as dict of pairtrees by prefix
        self.initialize_pairtrees()

        for htid in ids_to_index:
            if self.verbosity >= self.v_normal:
                self.stdout.write(htid)
            self.stats['count'] += 1

            digwork = self.import_digitizedwork(htid)
            # if no item is returned, either there is an error or no update
            # is needed; update count and go to the next item
            if not digwork:
                if progbar:
                    progbar.update(self.stats['count'])
                continue

            # count pages in the pairtree zip file and update digwork page count
            self.count_pages(digwork)

            if progbar:
                progbar.update(self.stats['count'])

        summary = '\nProcessed {:,d} item{} for import.' + \
        '\nAdded {:,d}; updated {:,d}; skipped {:,d}; {:,d} error{}; indexed {:,d} page{}.'
        summary = summary.format(
            self.stats['total'], pluralize(self.stats['total']),
            self.stats['created'], self.stats['updated'], self.stats['skipped'],
            self.stats['error'], pluralize(self.stats['error']),
            self.stats['pages'], pluralize(self.stats['pages'])
        )
        self.stdout.write(summary)

    def initialize_pairtrees(self):
        '''Initiaulize pairtree storage clients for each
        subdirectory in the configured **HATHI_DATA** path.'''

        # HathiTrust data is constructed with instutition short name
        # with pairtree root underneath each
        if not self.hathi_pairtree:
            hathi_dirs = glob(os.path.join(settings.HATHI_DATA, '*'))
            for ht_data_dir in hathi_dirs:
                prefix = os.path.basename(ht_data_dir)

                hathi_ptree = pairtree_client.PairtreeStorageClient(prefix, ht_data_dir)
                # store initialized pairtree client by prefix for later use
                self.hathi_pairtree[prefix] = hathi_ptree

    def get_hathi_ids(self):
        '''Generator of hathi ids from previously rsynced hathitrust data,
        based on the configured **HATHI_DATA** path in settings.'''

        self.initialize_pairtrees()
        for prefix, hathi_ptree in self.hathi_pairtree.items():
            for hathi_id in hathi_ptree.list_ids():
                # NOTE: prefix should automatially be handled based on
                # pairtree_prefix, but python pairtree library doesn't
                # yet include logic for that
                yield '%s.%s' % (prefix, hathi_id)

    def count_hathi_ids(self):
        '''count items in the pairtree structure without loading
        all into memory at once.'''
        start = time.time()
        count = sum(1 for i in self.get_hathi_ids())
        logger.debug('Counted hathi ids in %f sec' % (time.time() - start))
        return count

    def import_digitizedwork(self, htid):
        '''Import a single work into the database.
        Retrieves bibliographic data from Hathi api. If the record already
        exists in the database, it is only updated if the hathi record
        has changed or if an update is requested by the user.
        Creates admin log entry for record creation or record update.
        Returns None if there is an error retrieving bibliographic data
        or no update is needed; otherwise, returns the
        :class:`~ppa.archive.models.DigitizedWork`.'''

        # get bibliographic data for this record from Hathi api
        # - needed to check if update is required for existing records,
        #   and o populate metadata for new records
        try:
            # should only error on user-supplied ids, but still possible
            bibdata = self.bib_api.record('htid', htid)
        except HathiItemNotFound:
            self.stdout.write("Error: Bibliographic data not found for '%s'" % htid)
            self.stats['error'] += 1
            return

        # find existing record or create a new one
        digwork, created = DigitizedWork.objects.get_or_create(source_id=htid)

        if created:
            # create log entry for record creation
            LogEntry.objects.log_action(
                user_id=self.script_user.id,
                content_type_id=ContentType.objects.get_for_model(digwork).pk,
                object_id=digwork.pk,
                object_repr=str(digwork),
                change_message='Created via hathi_import script',
                action_flag=ADDITION)

        # if this is an existing record, check if updates are needed
        source_updated = None
        if not created and not self.options['update']:
            source_updated = bibdata.copy_last_updated(htid)
            if digwork.updated.date() > source_updated:
                # local copy is newer than last source modification date
                if self.verbosity > self.v_normal:
                    self.stdout.write('Source record last updated %s, no update needed'
                                      % source_updated)
                # nothing to do; continue to next item
                self.stats['skipped'] += 1
                return
            else:
                # report in verbose mode
                if self.verbosity > self.v_normal:
                    self.stdout.write('Source record last updated %s, updated needed'
                                      % source_updated)

        # update or populate digitized item in the database
        digwork.populate_from_bibdata(bibdata)
        digwork.save()

        if not created:
            # create log entry for updating an existing record
            # 0 include details about why the update happened if possible
            msg_detail = ''
            if self.options['update']:
                msg_detail = ' (forced update)'
            else:
                msg_detail = '; source record last updated %s' % source_updated

            LogEntry.objects.log_action(
                user_id=self.script_user.id,
                content_type_id=ContentType.objects.get_for_model(digwork).pk,
                object_id=digwork.pk,
                object_repr=str(digwork),
                change_message='Updated via hathi_import script%s' % msg_detail,
                action_flag=CHANGE)

        if created:
            self.stats['created'] += 1
        else:
            self.stats['updated'] += 1

        return digwork

    def count_pages(self, digwork):
        '''Count the number of pages for a digitized work in the
        pairtree content.'''

        # NOTE: this might be overkill now that we're no longer
        # indexing page content here, but should still be useful as
        # a sanity check

        # use existing pairtree client since it is already initialized
        ptree_client = self.hathi_pairtree[digwork.hathi_prefix]

        # count the files in the zipfile
        with ZipFile(digwork.hathi_zipfile_path(ptree_client)) as ht_zip:
            page_count = len(ht_zip.namelist())

        self.stats['pages'] += page_count

        # store page count in the database, if changed
        if digwork.page_count != page_count:
            digwork.page_count = page_count
            digwork.save()
