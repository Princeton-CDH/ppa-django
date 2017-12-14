from collections import defaultdict
from glob import glob
import os
import time
from zipfile import ZipFile

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.defaultfilters import pluralize
from pairtree import pairtree_path, pairtree_client
import progressbar

from ppa.archive.hathi import HathiBibliographicAPI, HathiItemNotFound
from ppa.archive.models import DigitizedWork
from ppa.archive.solr import get_solr_connection


class Command(BaseCommand):
    '''Import HathiTrust digitized items into PPA to be managed and searched'''
    help = __doc__

    solr = None
    solr_collection = None
    hathi_pairtree = {}
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

    def handle(self, *args, **kwargs):
        self.solr, self.solr_collection = get_solr_connection()
        bib_api = HathiBibliographicAPI()
        self.verbosity = kwargs.get('verbosity', self.v_normal)

        # bulk import only for now
        # - eventually support list of ids + rsync?

        # for now, start with existing rsync data
        # - get list of ids, rsync data, grab metadata
        # - populate db and solr (should add/update if already exists)

        stats = defaultdict(int)

        # if ids are explicitly specified on the command line, only
        # index those items
        # (currently still requires rsync data to be present on the filesystem)
        if kwargs['htids']:
            ids_to_index = kwargs['htids']
            stats['total'] = len(ids_to_index)
        else:
            # otherwise, find and index everything in the pairtree data
            ids_to_index = self.get_hathi_ids()
            stats['total'] = self.count_hathi_ids()

        if kwargs['progress']:
            progbar = progressbar.ProgressBar(redirect_stdout=True,
                max_value=stats['total'])
        else:
            progbar = None

        # initialize access to rsync data as dict of pairtrees by prefix
        self.initialize_pairtrees()

        for htid in ids_to_index:
            if self.verbosity >= self.v_normal:
                self.stdout.write(htid)
            stats['count'] += 1
            # get bibliographic data from Hathi api
            # - needed to check if update is required for existing records,
            # and needed to populate metadata for new records
            try:
                # should only error on user-supplied ids, but still possible
                bibdata = bib_api.record('htid', htid)
            except HathiItemNotFound:
                self.stdout.write("Error: Bibliographic data not found for '%s'" % htid)
                stats['error'] += 1
                continue

            # find existing record or create a new one
            digwork, created = DigitizedWork.objects.get_or_create(source_id=htid)
            # if this is an existing record, check if updates are needed
            if not created and not kwargs['update']:
                source_updated = bibdata.copy_last_updated(htid)
                if digwork.updated.date() > source_updated:
                    # local copy is newer than last source modification date
                    if self.verbosity > self.v_normal:
                        self.stdout.write('Source record last updated %s, no reindex needed'
                            % source_updated)
                    if progbar:
                        progbar.update(stats['count'])
                    # don't index; continue to next item
                    stats['skipped'] += 1
                    continue
                else:
                    # report in verbose mode
                    if self.verbosity > self.v_normal:
                        self.stdout.write('Source record last updated %s, needs reindexing'
                            % source_updated)

            # update or populate digitized item in the database
            digwork.populate_from_bibdata(bibdata)
            digwork.save()

            prefix, pt_id = htid.split('.', 1)
            # pairtree id to path for data files
            ptobj = self.hathi_pairtree[prefix].get_object(pt_id,
                create_if_doesnt_exist=False)
            # contents are stored in a directory named based on a
            # pairtree encoded version of the id
            content_dir = pairtree_path.id_encode(pt_id)
            # - expect a mets file and a zip file
            # - don't rely on them being returned in the same order on every machine
            parts = ptobj.list_parts(content_dir)
            # find the first zipfile in the list (should only be one)
            ht_zipfile = [part for part in parts if part.endswith('zip')][0]
            # currently not making use of the metsfile

            # create a list to gather solr information to index
            # digitized work and pages all at once
            solr_docs = [digwork.index_data()]
            # read zipfile contents in place, without unzipping
            with ZipFile(os.path.join(ptobj.id_to_dirpath(), content_dir, ht_zipfile)) as ht_zip:
                filenames = ht_zip.namelist()
                page_count = len(filenames)
                for pagefilename in filenames:
                    with ht_zip.open(pagefilename) as pagefile:
                        page_id = os.path.splitext(os.path.basename(pagefilename))[0]
                        solr_docs.append({
                           'id': '%s.%s' % (htid, page_id),
                           'srcid': htid,   # for grouping with work record
                           'content': pagefile.read().decode('utf-8'),
                           'order': page_id,
                           'item_type': 'page'
                        })
                self.solr.index(self.solr_collection, solr_docs,
                    params={"commitWithin": 10000})  # commit within 10 seconds

            stats['pages'] += len(solr_docs) - 1

            # store page count in the database after indexing pages
            digwork.page_count = page_count
            digwork.save()

            if created:
                stats['created'] += 1
            else:
                stats['updated'] += 1

            if progbar:
                progbar.update(stats['count'])

        # commit any indexed changes so they will be stored
        if stats['created'] or stats['updated']:
            self.solr.commit(self.solr_collection)

        summary = '\nProcessed {:,d} item{} for import.' + \
        '\nAdded {:,d}; updated {:,d}; skipped {:,d}; {:,d} error{}; indexed {:,d} page{}.'
        summary = summary.format(stats['total'], pluralize(stats['total']),
            stats['created'], stats['updated'], stats['skipped'],
            stats['error'], pluralize(stats['error']),
            stats['pages'], pluralize(stats['pages']))

        self.stdout.write(summary)

    def initialize_pairtrees(self):
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
        # generator of hathi ids from previously rsynced hathitrust data,
        # based on the configured path in settings

        self.initialize_pairtrees()
        for prefix, hathi_ptree in self.hathi_pairtree.items():
            for hathi_id in hathi_ptree.list_ids():
                # NOTE: prefix should automatially be handled based on
                # pairtree_prefix, but python pairtree library doesn't
                # yet include logic for that
                yield '%s.%s' % (prefix, hathi_id)


    def count_hathi_ids(self):
        # count items in the pairtree structure without loading
        # all into memory at once
        # NOTE: probably should still check how slow this is on
        # the full dataset...
        start = time.time()
        count = sum(1 for i in self.get_hathi_ids())
        if self.verbosity > self.v_normal:
            self.stdout.write('Counted hathi ids in %f sec' %
                (time.time() - start))
        return count


