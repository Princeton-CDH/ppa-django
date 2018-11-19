import json
import os.path
from time import sleep
import types
from unittest.mock import patch, Mock, DEFAULT
from zipfile import ZipFile

from django.conf import settings
from django.db.models.query import QuerySet
from django.test import TestCase, override_settings
from django.urls import reverse
from eulxml.xmlmap import load_xmlobject_from_file
from pairtree import pairtree_client, pairtree_path
import pytest

from ppa.archive import hathi
from ppa.archive.models import DigitizedWork, Collection
from ppa.archive.solr import get_solr_connection, Indexable


FIXTURES_PATH = os.path.join(settings.BASE_DIR, 'ppa', 'archive', 'fixtures')


class TestDigitizedWork(TestCase):
    fixtures = ['sample_digitized_works']

    bibdata_full = os.path.join(
        FIXTURES_PATH, 'bibdata_full_njp.32101013082597.json')
    bibdata_full2 = os.path.join(
        FIXTURES_PATH, 'bibdata_full_aeu.ark_13960_t1pg22p71.json')
    bibdata_brief = os.path.join(
        FIXTURES_PATH, 'bibdata_brief_njp.32101013082597.json')
    metsfile = os.path.join(FIXTURES_PATH, '79279237.mets.xml')

    def test_str(self):
        digwork = DigitizedWork(source_id='njp.32101013082597')
        assert str(digwork) == digwork.source_id

    def test_display_title(self):
        digwork = DigitizedWork(title='Elocutionary Language')
        assert digwork.display_title() == digwork.title

    @pytest.mark.usefixtures('solr')
    def test_index(self):
        with open(self.bibdata_brief) as bibdata:
            brief_bibdata = hathi.HathiBibliographicRecord(json.load(bibdata))

        digwork = DigitizedWork(source_id='njp.32101013082597')
        digwork.populate_from_bibdata(brief_bibdata)
        digwork.save()
        solr, solr_collection = get_solr_connection()
        # digwork should be unindexed
        res = solr.query(solr_collection, {'q': '*:*'})
        assert res.get_results_count() == 0
        # reindex to check that the method works on a saved object
        digwork.index()
        # digwork should be unindexed still because no commitWithin
        res = solr.query(solr_collection, {'q': '*:*'})
        assert res.get_results_count() == 0
        digwork.index(params={'commitWithin': 500})
        sleep(1)
        # digwork should be returned by a query
        res = solr.query(solr_collection, {'q': '*:*'})
        assert res.get_results_count() == 1
        assert res.docs[0]['id'] == 'njp.32101013082597'

    def test_populate_from_bibdata(self):
        with open(self.bibdata_full) as bibdata:
            full_bibdata = hathi.HathiBibliographicRecord(json.load(bibdata))

        with open(self.bibdata_brief) as bibdata:
            brief_bibdata = hathi.HathiBibliographicRecord(json.load(bibdata))

        digwork = DigitizedWork(source_id='njp.32101013082597')
        digwork.populate_from_bibdata(brief_bibdata)
        assert digwork.record_id == brief_bibdata.record_id
        assert digwork.title == brief_bibdata.title
        assert digwork.pub_date == brief_bibdata.pub_dates[0]
        # no enumcron in this record
        assert digwork.enumcron == ''
        # fields from marc not set
        assert not digwork.author
        assert not digwork.pub_place
        assert not digwork.publisher

        # test no pub date
        brief_bibdata.info['publishDates'] = []
        digwork = DigitizedWork(source_id='njp.32101013082597')
        digwork.populate_from_bibdata(brief_bibdata)
        assert not digwork.pub_date

        # TODO: test enumcron from copy details

        # populate from full record
        digwork.populate_from_bibdata(full_bibdata)
        # title and subtitle set from marc
        assert digwork.title == full_bibdata.marcxml['245']['a']
        assert digwork.subtitle == full_bibdata.marcxml['245']['b']
        # fixture has indicator 0, no non-sort characters
        assert digwork.sort_title == ' '.join([digwork.title, digwork.subtitle])
        # authors should have trailing period removed
        assert digwork.author == full_bibdata.marcxml.author().rstrip('.')
        # comma should be stripped from publication place and publisher
        assert digwork.pub_place == full_bibdata.marcxml['260']['a'].strip(',')
        assert digwork.publisher == full_bibdata.marcxml['260']['b'].strip(',')

        # second bibdata record with sort title
        with open(self.bibdata_full2) as bibdata:
            full_bibdata = hathi.HathiBibliographicRecord(json.load(bibdata))

        digwork = DigitizedWork(source_id='aeu.ark:/13960/t1pg22p71')
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.title == full_bibdata.marcxml['245']['a']
        # subtitle should omit last two characters (trailing space and slash)
        assert digwork.subtitle == full_bibdata.marcxml['245']['b'][:-2]
        # fixture has title with non-sort characters
        assert digwork.sort_title == ' '.join([
            digwork.title[int(full_bibdata.marcxml['245'].indicators[1]):],
            full_bibdata.marcxml['245']['b']
        ])
        # store title before modifying it for tests
        orig_bibdata_title = full_bibdata.marcxml['245']['a']

        # test error in record (title non-sort character non-numeric)
        with open(self.bibdata_full2) as bibdata:
            full_bibdata = hathi.HathiBibliographicRecord(json.load(bibdata))
            full_bibdata.marcxml['245'].indicators[1] = ' '
            digwork.populate_from_bibdata(full_bibdata)
            assert digwork.sort_title == \
                ' '.join([digwork.title, full_bibdata.marcxml['245']['b']])

            # test error in title sort (doesn't include space after definite article)
            full_bibdata.marcxml['245'].indicators[1] = 3
            digwork.populate_from_bibdata(full_bibdata)
            assert not digwork.sort_title.startswith(' ')

            # test cleaning up leading punctuation
            full_bibdata.marcxml['245'].indicators[1] = 0
            full_bibdata.marcxml['245']['a'] = '"Elocutionary Language."'
            digwork.populate_from_bibdata(full_bibdata)
            assert not digwork.sort_title.startswith('"')

            full_bibdata.marcxml['245']['a'] = "[Pamphlets on Language.]"
            digwork.populate_from_bibdata(full_bibdata)
            assert not digwork.sort_title.startswith('[')

        # test title cleanup
        full_bibdata.marcxml['245']['a'] = orig_bibdata_title
        # - remove trailing slash from title
        full_bibdata.marcxml['245']['a'] += ' /'
        digwork.populate_from_bibdata(full_bibdata)
        # title should omit last two characters
        assert digwork.title == orig_bibdata_title
        # - remove initial open bracket
        full_bibdata.marcxml['245']['a'] = '[{}'.format(orig_bibdata_title)
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.title == orig_bibdata_title
        # - internal brackets should be unchanged
        full_bibdata.marcxml['245']['a'] = 'A third[-fourth] class reader.'
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.title == full_bibdata.marcxml['245']['a']

        # author trailing period not removed for single initials
        # - name with initials, no date
        full_bibdata.marcxml['100']['a'] = 'Mitchell, M. S.'
        full_bibdata.marcxml['100']['d'] = ''
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.author == full_bibdata.marcxml['100']['a']
        # - initials with no space
        full_bibdata.marcxml['100']['a'] = 'Mitchell, M.S.'
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.author == full_bibdata.marcxml['100']['a']
        # - esquire
        full_bibdata.marcxml['100']['a'] = 'Wilson, Richard, Esq.'
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.author == full_bibdata.marcxml['100']['a']
        # - remove '[from old catalog]'
        full_bibdata.marcxml['100']['a'] = 'Thurber, Samuel. [from old catalog]'
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.author == 'Thurber, Samuel'

        # sine loco/nomine should be cleared out
        full_bibdata.marcxml['260']['a'] = '[S.l.]'
        full_bibdata.marcxml['260']['b'] = '[s.n.]'
        digwork.populate_from_bibdata(full_bibdata)
        assert not digwork.pub_place
        assert not digwork.publisher

        # brackets around publisher and pub place should be removed
        full_bibdata.marcxml['260']['a'] = '[London]'
        full_bibdata.marcxml['260']['b'] = '[Faber]'
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.pub_place == full_bibdata.marcxml['260']['a'].strip('[]')
        assert digwork.publisher == full_bibdata.marcxml['260']['b'].strip('[]')
        full_bibdata.marcxml['260']['a'] = 'New Brunswick [N.J.]'
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.pub_place == full_bibdata.marcxml['260']['a']

        # clean up publisher preliminary text
        publisher = 'James Humphreys'
        variants =  [
            'Printed at',
            'Printed and sold by',
            'Printed and published by',
            'Pub. for',
            'Published for the',
            'Publisht for the',
        ]
        for prefix in variants:
            full_bibdata.marcxml['260']['b'] = ' '.join([prefix, publisher])
            digwork.populate_from_bibdata(full_bibdata)
            assert digwork.publisher == publisher

        # handle subtitle, publisher, place of publication unset
        full_bibdata.marcxml['245']['b'] = None
        full_bibdata.marcxml['260']['a'] = None
        full_bibdata.marcxml['260']['b'] = None
        digwork.populate_from_bibdata(full_bibdata)
        assert digwork.subtitle == ''
        assert digwork.pub_place == ''
        assert digwork.publisher == ''

        # NOTE: not currently testing publication info unavailable

    def test_index_data(self):
        digwork = DigitizedWork.objects.create(
            source_id='njp.32101013082597',
            title='The Structure of English Verse', pub_date=1884,
            subtitle='An essay',
            sort_title='Structure of English Verse',
            author='Charles Witcomb', pub_place='Paris',
            publisher='Mesnil-Dramard',
            source_url='https://hdl.handle.net/2027/njp.32101013082597',
            public_notes='A note field here')
        coll1 = Collection.objects.create(name='Flotsam')
        coll2 = Collection.objects.create(name='Jetsam')
        digwork.collections.add(coll1)
        digwork.collections.add(coll2)
        index_data = digwork.index_data()
        assert index_data['id'] == digwork.source_id
        assert index_data['srcid'] == digwork.source_id
        assert index_data['item_type'] == 'work'
        assert index_data['title'] == digwork.title
        assert index_data['subtitle'] == digwork.subtitle
        assert index_data['sort_title'] == digwork.sort_title
        assert index_data['author'] == digwork.author
        assert index_data['pub_place'] == digwork.pub_place
        assert index_data['pub_date'] == digwork.pub_date
        assert index_data['collections'] == ['Flotsam', 'Jetsam']
        assert index_data['publisher'] == digwork.publisher
        assert index_data['src_url'] == digwork.source_url
        assert digwork.public_notes in index_data['text']
        assert digwork.notes not in index_data['text']
        assert not index_data['enumcron']

        # with enumcron
        digwork.enumcron = 'v.7 (1848)'
        assert digwork.index_data()['enumcron'] == digwork.enumcron

    def test_get_absolute_url(self):
        work = DigitizedWork.objects.first()
        assert work.get_absolute_url() == \
            reverse('archive:detail', kwargs={'source_id': work.source_id})

    @patch('ppa.archive.models.HathiBibliographicAPI')
    def test_get_metadata(self, mock_hathibib):
        work = DigitizedWork(source_id='ht:1234')

        # unsupported metadata format should error
        with pytest.raises(ValueError):
            work.get_metadata('bogus')

        # for marc, should call hathi bib api and return marc in binary form
        mdata = work.get_metadata('marc')
        mock_hathibib.assert_any_call()
        mock_bibapi = mock_hathibib.return_value
        mock_bibapi.record.assert_called_with('htid', work.source_id)
        mock_bibdata = mock_bibapi.record.return_value
        mock_bibdata.marcxml.as_marc.assert_any_call()
        assert mdata == mock_bibdata.marcxml.as_marc.return_value

    def test_hathi_prefix(self):
        work = DigitizedWork(source_id='uva.1234')
        assert work.hathi_prefix == 'uva'

    def test_hathi_pairtree_id(self):
        work = DigitizedWork(source_id='uva.1234')
        assert work.hathi_pairtree_id == '1234'

    def test_hathi_content_dir(self):
        work = DigitizedWork(source_id='uva.1234')
        assert work.hathi_content_dir == pairtree_path.id_encode(work.hathi_pairtree_id)

    @patch('ppa.archive.models.pairtree_client')
    @override_settings(HATHI_DATA='/tmp/ht_text_pd')
    def test_hathi_pairtree_object(self, mock_pairtree_client):
        work = DigitizedWork(source_id='uva.1234')

        ptree_obj = work.hathi_pairtree_object()
        # client initialized
        mock_pairtree_client.PairtreeStorageClient \
            .assert_called_with(work.hathi_prefix,
                                os.path.join(settings.HATHI_DATA, work.hathi_prefix))
        # object retrieved
        mock_pairtree_client.PairtreeStorageClient.return_value \
            .get_object.assert_called_with(work.hathi_pairtree_id,
                                           create_if_doesnt_exist=False)
        # object returned
        assert ptree_obj == mock_pairtree_client.PairtreeStorageClient  \
                                                .return_value.get_object.return_value

        # test passing in existing pairtree client
        mock_pairtree_client.reset_mock()
        my_ptree_client = Mock(spec=pairtree_client.PairtreeStorageClient)
        ptree_obj = work.hathi_pairtree_object(my_ptree_client)
        # should not initialize
        mock_pairtree_client.PairtreeStorageClient.assert_not_called()
        # should get object from my client
        my_ptree_client.get_object.assert_called_with(work.hathi_pairtree_id,
                                           create_if_doesnt_exist=False)

    @override_settings(HATHI_DATA='/tmp/ht_text_pd')
    def test_hathi_zipfile_path(self):
        work = DigitizedWork(source_id='chi.79279237')
        contents = ['79279237.mets.xml', '79279237.zip']

        with patch.object(DigitizedWork, 'hathi_pairtree_object') as mock_ptree_obj_meth:
            mock_ptree_obj = mock_ptree_obj_meth.return_value
            mock_ptree_obj.list_parts.return_value = contents
            mock_ptree_obj.id_to_dirpath.return_value = \
                '/tmp/ht_text_pd/chi/pairtree_root/79/27/92/37'

            zipfile_path = work.hathi_zipfile_path()
            mock_ptree_obj_meth.assert_called_with(ptree_client=None)
            assert zipfile_path == \
                os.path.join(mock_ptree_obj.id_to_dirpath(), work.hathi_content_dir,
                             contents[1])

            # use pairtree client object if passed in
            my_ptree_client = Mock(spec=pairtree_client.PairtreeStorageClient)
            work.hathi_zipfile_path(my_ptree_client)
            mock_ptree_obj_meth.assert_called_with(ptree_client=my_ptree_client)

    @override_settings(HATHI_DATA='/tmp/ht_text_pd')
    def test_hathi_metsfile_path(self):
        work = DigitizedWork(source_id='chi.79279237')
        contents = ['79279237.mets.xml', '79279237.zip']

        with patch.object(DigitizedWork, 'hathi_pairtree_object') as mock_ptree_obj_meth:
            mock_ptree_obj = mock_ptree_obj_meth.return_value
            mock_ptree_obj.list_parts.return_value = contents
            mock_ptree_obj.id_to_dirpath.return_value = \
                '/tmp/ht_text_pd/chi/pairtree_root/79/27/92/37'

            metsfile_path = work.hathi_metsfile_path()
            mock_ptree_obj_meth.assert_called_with(ptree_client=None)
            assert metsfile_path == \
                os.path.join(mock_ptree_obj.id_to_dirpath(), work.hathi_content_dir,
                             contents[0])

            # use pairtree client object if passed in
            my_ptree_client = Mock(spec=pairtree_client.PairtreeStorageClient)
            work.hathi_metsfile_path(my_ptree_client)
            mock_ptree_obj_meth.assert_called_with(ptree_client=my_ptree_client)

    @patch('ppa.archive.models.ZipFile', spec=ZipFile)
    @override_settings(HATHI_DATA='/tmp/ht_text_pd')
    def test_page_index_data(self, mockzipfile):
        mockzip_obj = mockzipfile.return_value.__enter__.return_value
        page_files = ['0001.txt', '00002.txt']
        mockzip_obj.namelist.return_value = page_files
        # simulate reading zip file contents
        contents = ('page content for one', 'hello! pshaw! what?')
        mockzip_obj.open.return_value.__enter__.return_value \
            .read.return_value.decode.side_effect = contents

        work = DigitizedWork(source_id='chi.79279237')

        # page data comes from mets
        mets = load_xmlobject_from_file(self.metsfile, hathi.MinimalMETS)

        with patch.multiple(DigitizedWork, hathi_zipfile_path=DEFAULT,
                            hathi_metsfile_path=DEFAULT) as \
                            mock_methods:
            mock_methods['hathi_zipfile_path'].return_value = '/path/to/79279237.zip'
            mock_methods['hathi_metsfile_path'].return_value = self.metsfile

            page_data = work.page_index_data()
            assert isinstance(page_data, types.GeneratorType)

            for i, data in enumerate(page_data):
                mets_page = mets.structmap_pages[i]
                assert data['id'] == '.'.join([work.source_id, mets_page.text_file.sequence])
                assert data['srcid'] == work.source_id
                assert data['content'] == contents[i]
                assert data['order'] == mets_page.order
                assert data['item_type'] == 'page'
                assert data['label'] == mets_page.display_label
                assert 'tags' in data
                assert data['tags'] == mets_page.label.split(', ')


    def test_index_id(self):
        work = DigitizedWork(source_id='chi.79279237')
        assert work.index_id() == work.source_id

    @patch.object(Indexable, 'index_items')
    def test_handle_collection_save(self, mock_index_items):
        digwork = DigitizedWork.objects.create(source_id='njp.32101013082597')
        coll1 = Collection.objects.create(name='Flotsam')
        digwork.collections.add(coll1)

        DigitizedWork.handle_collection_save(Mock(), coll1)
        # index not called because collection name has not changed
        mock_index_items.assert_not_called()

        # modify name to test indexing
        coll1.name = 'Jetsam'
        DigitizedWork.handle_collection_save(Mock(), coll1)
        # call must be inspected piecemeal because queryset equals comparison fails
        args, kwargs = mock_index_items.call_args
        assert isinstance(args[0], QuerySet)
        assert digwork in args[0]
        assert kwargs['params'] == {'commitWithin': 3000}

    @patch.object(Indexable, 'index_items')
    def test_handle_collection_delete(self, mock_index_items):
        digwork = DigitizedWork.objects.create(source_id='njp.32101013082597')
        coll1 = Collection.objects.create(name='Flotsam')
        digwork.collections.add(coll1)

        DigitizedWork.handle_collection_delete(Mock(), coll1)

        assert coll1.digitizedwork_set.count() == 0
        args, kwargs = mock_index_items.call_args
        assert isinstance(args[0], QuerySet)
        assert digwork in args[0]
        assert kwargs['params'] == {'commitWithin': 3000}


class TestCollection(TestCase):
    fixtures = ['sample_digitized_works']

    def test_str(self):
        collection = Collection(name='Random Assortment')
        assert str(collection) == 'Random Assortment'

    def test_name_changed(self):
        collection = Collection(name='Random Assortment')
        assert not collection.name_changed
        # change the name
        collection.name = 'Randomer'
        assert collection.name_changed
        # save changes; should no longer be marked as changed
        collection.save()
        assert not collection.name_changed

    @pytest.mark.usefixtures("solr")
    def test_stats(self):
        # test collection stats from Solr

        coll1 = Collection.objects.create(name='Random Grabbag')
        coll2 = Collection.objects.create(
            name='Foo through Time',
            description="A <em>very</em> useful collection."
        )

        # add items to collections
        # - put everything in collection 1
        digworks = DigitizedWork.objects.all()
        for digwork in digworks:
            digwork.collections.add(coll1)
        # just one item in collection 2
        wintry = digworks.get(title__icontains='Wintry')
        wintry.collections.add(coll2)

        # reindex the digitized works so we can check stats
        solr, solr_collection = get_solr_connection()
        solr.index(solr_collection, [dw.index_data() for dw in digworks],
                   params={"commitWithin": 100})
        sleep(2)

        stats = Collection.stats()
        assert stats[coll1.name]['count'] == digworks.count()
        assert stats[coll1.name]['dates'] == '1880–1904'
        assert stats[coll2.name]['count'] == 1
        assert stats[coll2.name]['dates'] == '1903'

