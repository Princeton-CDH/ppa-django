from glob import glob
import os
import time
from zipfile import ZipFile

from django.conf import settings
from django.core.management.base import BaseCommand
from pairtree import pairtree_path, pairtree_client

from ppa.archive.hathi import HathiBibliographicAPI
from ppa.archive.models import DigitizedWork
from ppa.archive.solr import get_solr_connection


class Command(BaseCommand):
    '''Import digitized items into PPA to be managed and searched'''
    help = __doc__

    solr = None
    solr_collection = None
    hathi_pairtree = {}
    #: normal verbosity level
    v_normal = 1

    def add_arguments(self, parser):
        parser.add_argument('-u', '--update', action='store_true',
            help='''Update local content even if source record has not changed.''')

    def handle(self, *args, **kwargs):
        self.solr, self.solr_collection = get_solr_connection()
        bib_api = HathiBibliographicAPI()
        self.verbosity = kwargs.get('verbosity', self.v_normal)

        # bulk import only for now
        # - eventually support list of ids + rsync?
        # for now, start with existing rsync data
        # - get list of ids, rsync data, grab metadata
        # - populate db and solr (should add/update if already exists)
        total = self.count_hathi_ids()
        self.stdout.write('%d items to import' % total)
        for htid in self.get_hathi_ids():
            if self.verbosity >= self.v_normal:
                self.stdout.write(htid)
            # find existing record or create a new one
            digwork, created = DigitizedWork.objects.get_or_create(source_id=htid)
            # get bibliographic data from Hathi api
            # - needed to check if update is required for existing records,
            # and needed to populate metadata for new records
            bibdata = bib_api.record('htid', htid)
            # if this is an existing record, check if updates are needed
            if not created and not kwargs['update']:
                source_updated = bibdata.copy_last_updated(htid)
                if digwork.updated.date() > source_updated:
                    # local copy is newer than last source modification date
                    if self.verbosity > self.v_normal:
                        self.stdout.write('Source record last updated %s, no reindex needed'
                            % source_updated)
                    # don't index; continue to next item
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
            ht_metsfile, ht_zipfile = ptobj.list_parts(content_dir)

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
                self.solr.index(self.solr_collection, solr_docs)

            # store page count in the database after indexing pages
            digwork.page_count = page_count
            digwork.save()

        # commit newly indexed changes so they will be visible for searches
        # FIXME: this doesn't seem to be working consistently; (maybe
        # only in tandem with schema changes?)
        self.solr.commit(self.solr_collection)

    def get_hathi_ids(self):
        # generator of hathi ids from previously rsynced hathitrust data,
        # based on the configured path in settings

        # HathiTrust data is constructed with instutition short name
        # with pairtree root underneath each
        hathi_dirs = glob(os.path.join(settings.HATHI_DATA, '*'))
        for ht_data_dir in hathi_dirs:
            prefix = os.path.basename(ht_data_dir)

            hathi_ptree = pairtree_client.PairtreeStorageClient(prefix, ht_data_dir)
            # store initialized pairtree client by prefix for later use
            self.hathi_pairtree[prefix] = hathi_ptree
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


