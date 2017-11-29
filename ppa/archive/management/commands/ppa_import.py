from glob import glob
import os
from zipfile import ZipFile

from django.conf import settings
from django.core.management.base import BaseCommand
from SolrClient import SolrClient
from pairtree import pairtree_path, pairtree_client

from ppa.archive.hathi import HathiBibliographicAPI
from ppa.archive.models import DigitizedWork


class Command(BaseCommand):
    '''Import digitized items into PPA to be managed and searched'''
    help = __doc__

    solr = None
    solr_collection = None
    hathi_pairtree = {}

    def handle(self, *args, **kwargs):
        # TODO: error handling etc
        solr_config = settings.SOLR_CONNECTIONS['default']

        self.solr = SolrClient(solr_config['URL'])
        self.solr_collection = solr_config['COLLECTION']
        bib_api = HathiBibliographicAPI()

        # bulk import only for now
        # - eventually support list of ids + rsync?
        # for now, start with existing rsync data
        # - get list of ids, rsync data, grab metadata
        # - populate db and solr (should add/update if already exists)

        for htid in self.get_hathi_ids():
            print(htid)
            prefix, pt_id = htid.split('.', 1)
            # pairtree id to path for data files
            ptobj = self.hathi_pairtree[prefix].get_object(pt_id,
                create_if_doesnt_exist=False)
            # contents are stored in a directory named based on a
            # pairtree encoded version of the id
            content_dir = pairtree_path.id_encode(pt_id)
            # - expect a mets file and a zip file
            ht_metsfile, ht_zipfile = ptobj.list_parts(content_dir)
            # print(ptobj.list_parts(pairtree_path.id_encode(pt_id)))
            solr_docs = []
            # read zipfile contents in place, without unzipping
            with ZipFile(os.path.join(ptobj.id_to_dirpath(), content_dir, ht_zipfile)) as ht_zip:
                filenames = ht_zip.namelist()
                page_count = len(filenames)
                for pagefilename in filenames:
                    with ht_zip.open(pagefilename) as pagefile:
                        page_id = os.path.splitext(os.path.basename(pagefilename))[0]
                        solr_docs.append({
                           'id': '%s.%s' % (htid, page_id),
                           'htid': htid,
                           'content': pagefile.read().decode('utf-8'),
                           'item_type': 'page'
                        })
                # print(len(ht_zip.namelist()))
                idx = self.solr.index(self.solr_collection, solr_docs)

            # create stub database record
            digwork, created = DigitizedWork.objects.get_or_create(source_id=htid)

            # get brief bibliographic record from hathi bib api
            bibdata = bib_api.record('htid', htid)
            if bibdata:
                digwork.title = bibdata.title
                # NOTE: may also include sort title
                # pub date is list; just use first for now (if available)
                if bibdata.pub_dates:
                    digwork.pub_date = bibdata.pub_dates[0]
                copy_details = bibdata.copy_details(htid)
                digwork.enumcron = copy_details['enumcron'] or ''
                if bibdata.marcxml:
                    digwork.author = bibdata.marcxml.author() or ''

                # TODO: should also consider storing:
                # - last update, rights code / rights string, item url
                # (maybe solr only?)

            digwork.page_count = page_count
            # TODO: only save if changed (so updated time will be accurate)
            digwork.save()

            # update work details in solr
            # TODO: solrdoc method on model
            solr_doc = {'id': htid, 'htid': htid, 'item_type': 'work', 'title': digwork.title,
                        'pub_date': digwork.pub_date, 'enumcron': digwork.enumcron,
                        'author': digwork.author}
            idx = self.solr.index(self.solr_collection, [solr_doc])

        self.solr.commit(self.solr_collection)

    def get_hathi_ids(self):
        # generator of hathi ids from previously rsynced hathitrust data

        # HathiTrust data is constructed with instutition short name
        # with pairtree root underneath each
        hathi_dirs = glob(os.path.join(settings.HATHI_DATA, '*'))
        for ht_data_dir in hathi_dirs:
            prefix = os.path.basename(ht_data_dir)
            # rsync data provided by hathi doesn't include version file,
            # but according to python pairtree package that's invalid'
            # - create version file if it doesn't exist
            # ptree_version = os.path.join(ht_data_dir, 'pairtree_version0_1')
            # if not os.path.exists(ptree_version):
            #     with open(ptree_version, 'w'):
            #         pass

            # maybe store the pairtree clients by prefix?
            hathi_ptree = pairtree_client.PairtreeStorageClient(prefix, ht_data_dir)
            # store initialized pairtree for later use
            self.hathi_pairtree[prefix] = hathi_ptree
            for hathi_id in hathi_ptree.list_ids():
                # NOTE: prefix should automatially be handled based on
                # pairtree_prefix, but python pairtree library doesn't
                # yet include logic for that
                yield '%s.%s' % (prefix, hathi_id)


