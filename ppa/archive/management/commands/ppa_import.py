from glob import glob
import os
from zipfile import ZipFile

from django.conf import settings
from django.core.management.base import BaseCommand
from SolrClient import SolrClient
from pairtree import pairtree_path, pairtree_client
import pandas

from ppa.archive.models import DigitizedWork


class Command(BaseCommand):
    '''Import digitized items into PPA to be managed and searched'''
    help = __doc__

    solr = None
    solr_collection = None
    hathi_pairtree = {}
    hathfiles_columns = ['volume_id', 'access', 'rights', 'htbibid',
        'enumchron', 'source', 'source_inst_id', 'oclc', 'isbn', 'issn',
        'lccn', 'title', 'imprint', 'rights_code', 'updated', 'govdoc',
        'publication_date', 'publication_place', 'language', 'bib_format',
        'coll_code', 'content_provider', 'resp_entity', 'digitization_agent'
        ]

    def handle(self, *args, **kwargs):
        # TODO: error handling etc
        solr_config = settings.SOLR_CONNECTIONS['default']

        self.solr = SolrClient(solr_config['URL'])
        self.solr_collection = solr_config['COLLECTION']

        # hathifile_metadata = read_table(settings.HATHIFILES,
        #     header=None, index_col=0)
        # print(hathifile_metadata)
        # print(hathifile_metadata.index)

        # bulk import only for now
        # - eventually support list of ids + rsync?
        # for now, start with existing rsync data
        # - get list of ids, rsync data, grab metadata
        # - populate db and solr (should add/update if already exists)

        for htid in self.get_hathi_ids():
            print(htid)
            # try:
            #     print(hathifile_metadata.loc[htid])
            # except:
            #     print('%s not in hathifile' % htid)

            prefix, pt_id = htid.split('.', 1)
            print('ptid = %s' % pt_id)
            # pairtree id to path for data files
            ptobj = self.hathi_pairtree[prefix].get_object(pt_id,
                create_if_doesnt_exist=False)
            print(ptobj.id_to_dirpath())
            # contents are stored in a directory named based on a
            # pairtree encoded version of the id
            content_dir = pairtree_path.id_encode(pt_id)
            # - expect a mets file and a zip file
            ht_metsfile, ht_zipfile = ptobj.list_parts(content_dir)
            # print(ptobj.list_parts(pairtree_path.id_encode(pt_id)))
            print(ht_zipfile)
            solr_docs = []
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
            digwork.page_count = page_count
            # TODO: only save if changed (so updated time will be accurate)
            digwork.save()

            idx = self.solr.index(self.solr_collection, [{'id': htid, 'item_type': 'work'}])
            print(idx)

        self.solr.commit(self.solr_collection)

        # get bibliographic metadata
        # json api
        # max 20 records at a time; full or brief record
        # syntax for multiple is htid:id.1|htid:id.2|htid:id.3
    # https://catalog.hathitrust.org/api/volumes/full/json/htid:njp.32101013082597%7Chtid:hvd.32044011432754%7Chtid:chi.085137191

        count = 0
        with open(settings.HATHIFILES) as hathimetadata:
            for line in hathimetadata:
                count += 1
                meta_id, data = line.split('\t', 1)
                # print("metaid %s" % meta_id)
                results = self.solr.query(self.solr_collection, {
                    'q': 'item_type:work AND id:"%s"' % meta_id,
                    'fl': 'id',
                    # 'rows': 0
                })
                if results.get_results_count():
                    print('found match for %s' % meta_id)
                    item_info = data.split('\t')
                    print(item_info[10]) # title
                    print(item_info[15]) # pub date
                    print(item_info[16]) # pub place

                    solr_doc = {'id': meta_id, 'item_type': 'work', 'title': item_info[10],
                        'pub_date': item_info[15]}
                    print(solr_doc)
                    idx = self.solr.index(self.solr_collection, [solr_doc])

                if count % 1000 == 0:
                    print(count)


            print(count)
            # - create stub record
            # - add metadata to solr
            # get pages
            # - add to solr

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
            ptree_version = os.path.join(ht_data_dir, 'pairtree_version0_1')
            if not os.path.exists(ptree_version):
                with open(ptree_version, 'w'):
                    pass

            # maybe store the pairtree clients by prefix?
            hathi_ptree = pairtree_client.PairtreeStorageClient(prefix, ht_data_dir)
            # store initialized pairtree for later use
            self.hathi_pairtree[prefix] = hathi_ptree
            for hathi_id in hathi_ptree.list_ids():
                yield '%s.%s' % (prefix, hathi_id)


