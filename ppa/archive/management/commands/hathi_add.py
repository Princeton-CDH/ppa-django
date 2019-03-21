'''
**hathi_add** is a custom manage command for adding new HathiTrust
records to the local database *and* to the local pairtree datastore.
For records that are already in the local pairtree, use **hathi_import**.

Example usage::

    # add items by id on the command line
    python manage.py hathi_add htid1 htid2 htid3
    # add items by one id per line in a text file
    python manage.py --file path/to/idfile.txt

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
        parser.add_argument(
            '--file', '-f',
            help='Filename with a list of HathiTrust ids to add (one per line).')

    def handle(self, *args, **kwargs):
        # disconnect signal handler for on-demand indexing, for efficiency
        # (index in bulk after an update, not one at a time)
        IndexableSignalHandler.disconnect()

        self.bib_api = HathiBibliographicAPI()
        self.verbosity = kwargs.get('verbosity', self.v_normal)
        self.options = kwargs

        self.stats = defaultdict(int)
        htids = self.ids_to_process()

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

    def ids_to_process(self):
        '''Determine Hathi ids to be processed. Checks list of ids
        on the command line and file if specified and filters out
        any ids already present in the database.'''
        htids = self.options['htids']
        # if id file is specified, get ids from the file
        if self.options['file']:
            with open(self.options['file']) as idfile:
                # add all non-empty lines with whitespace removed
                htids.extend([line.strip() for line in idfile.readlines()
                              if line.strip()])

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

        return htids

    def add_digitizedwork(self, htid):
        '''Add a new work to the database and its data to the file store.'''

        # store the current time to find log entries created after
        before = now()

        try:
            digwork = DigitizedWork.add_from_hathi(
                htid, self.bib_api, get_data=True,
                log_msg_src='via hathi_add script')

        except HathiItemNotFound:
            self.stderr.write("Error: record not found for '%s'" % htid)
            self.stats['error'] += 1
            return

        except HathiItemForbidden:
            # currently the only place this can fail is data aggregate request
            self.stderr.write("Error: data access not allowed for '%s'" % htid)
            self.stats['error'] += 1
            # remove the partial record
            DigitizedWork.objects.filter(source_id=htid).delete()
            return

        log_entry = LogEntry.objects.filter(object_id=digwork.id,
                                            action_time__gt=before).first()

        # track successful creation of a new record
        if log_entry and log_entry.action_flag == ADDITION:
            self.stats['created'] += 1
        # NOTE: currently hathi data is only retrieved for new records,
        # so ignoring updates here (metadata changes only)
        self.stats['pages'] += digwork.page_count

        return digwork
