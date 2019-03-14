'''
**hathi_add** is a custom manage command for adding new HathiTrust
records to the local database *and* to the local pairtree datastore.
For records that are already in the local pairtree, use **hathi_import**.

Example usage::

    # add specific items
    python manage.py hathi_add htid1 htid2 htid3

'''


from collections import defaultdict
import logging
import os
import time

from django.conf import settings
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.template.defaultfilters import pluralize
from django.utils.timezone import now
import progressbar

from ppa.archive.hathi import HathiBibliographicAPI, HathiItemNotFound, \
    HathiItemForbidden
from ppa.archive.models import DigitizedWork
from ppa.archive.signals import IndexableSignalHandler
from ppa.archive.solr import Indexable, get_solr_connection


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
        parser.add_argument(
            'htids', nargs='*',
            help='Optional list of specific volumes to add by HathiTrust id.')
        # TODO: also support file with list of ids
        # parser.add_argument(
        #     '--progress', action='store_true',
        #     help='Display a progress bar to track the status of the import.')

    def handle(self, *args, **kwargs):
        # disconnect signal handler for on-demand indexing, for efficiency
        # (index in bulk after an update, not one at a time)
        IndexableSignalHandler.disconnect()

        self.bib_api = HathiBibliographicAPI()
        self.verbosity = kwargs.get('verbosity', self.v_normal)
        self.options = kwargs
        # self.digwork_content_type = ContentType.objects.get_for_model(DigitizedWork)

        self.stats = defaultdict(int)
        htids = self.options['htids']
        self.stats['total'] = len(htids)

        # check for any ids that are in the database and skip them
        existing_ids = DigitizedWork.objects.filter(source_id__in=htids) \
            .values_list('source_id', flat=True)

        if existing_ids:
            self.stats['skipped'] += len(existing_ids)
            if self.verbosity >= self.v_normal:
                self.stdout.write('Skipping ids already present: %s' %
                                  ', '.join(existing_ids))

        # only process ids that are not already present in the database
        htids = set(htids) - set(existing_ids)

        works = []
        for htid in htids:
            if self.verbosity >= self.v_normal:
                self.stdout.write('Adding %s' % htid)

            self.stats['count'] += 1
            digwork = self.add_digitizedwork(htid)
            if digwork:
                works.append(digwork)

        # index the new content - both metadata and full text
        if works:
            Indexable.index_items(works)
            for work in works:
                # index page index data in chunks (returns a generator)
                Indexable.index_items(work.page_index_data())

            solr, solr_collection = get_solr_connection()
            solr.commit(solr_collection, openSearcher=True)

        summary = '\nProcessed {:,d} item{}.' + \
        '\nAdded {:,d}; skipped {:,d}; {:,d} error{}; imported {:,d} page{}.'
        summary = summary.format(
            self.stats['total'], pluralize(self.stats['total']),
            self.stats['created'], self.stats['skipped'],
            self.stats['error'], pluralize(self.stats['error']),
            self.stats['pages'], pluralize(self.stats['pages'])
        )
        self.stdout.write(summary)

    def add_digitizedwork(self, htid):
        '''Add a new work to the database and its data to the file store.'''

        # store the current time to find log entries created after
        before = now()

        try:
            digwork = DigitizedWork.add_from_hathi(
                htid, self.bib_api, get_data=True,
                log_msg_src='via hathi_add script')

        except HathiItemNotFound:
            self.stderr.write("Error: Record not found for '%s'" % htid)
            self.stats['error'] += 1
            return

        except HathiItemForbidden:
            # currently the only place this can fail is data aggregate request
            self.stderr.write("Error: data access not allowed for '%s'" % htid)
            self.stats['error'] += 1
            # remove the partial record
            DigitizedWork.objects.filter(source_id=htid).delete()
            return

        # track success
        self.stats['created'] += 1
        self.stats['pages'] += digwork.page_count

        return digwork
