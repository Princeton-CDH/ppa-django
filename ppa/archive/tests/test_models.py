import json
import os.path
from time import sleep
from unittest.mock import call, patch


import pytest
from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from ppa.archive import hathi
from ppa.archive.models import DigitizedWork, Collection
from ppa.archive.solr import get_solr_connection

FIXTURES_PATH = os.path.join(settings.BASE_DIR, 'ppa', 'archive', 'fixtures')


class TestDigitizedWork(TestCase):
    fixtures = ['sample_digitized_works']

    bibdata_full = os.path.join(FIXTURES_PATH,
        'bibdata_full_njp.32101013082597.json')
    bibdata_brief = os.path.join(FIXTURES_PATH,
        'bibdata_brief_njp.32101013082597.json')

    def test_str(self):
        digwork = DigitizedWork(source_id='njp.32101013082597')
        assert str(digwork) == digwork.source_id

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
        # digwork should be unindexed still because no commit
        res = solr.query(solr_collection, {'q': '*:*'})
        assert res.get_results_count() == 0
        digwork.index(commit=True)
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
        assert digwork.author == full_bibdata.marcxml.author()
        assert digwork.pub_place == full_bibdata.marcxml['260']['a']
        assert digwork.publisher == full_bibdata.marcxml['260']['b']

        # TODO: test publication info unavailable?

    def test_index_data(self):
        digwork = DigitizedWork.objects.create(source_id='njp.32101013082597',
            title='Structure of English Verse', pub_date=1884,
            author='Charles Witcomb', pub_place='Paris',
            publisher='Mesnil-Dramard',
            source_url='https://hdl.handle.net/2027/njp.32101013082597')
        coll1 = Collection.objects.create(name='Flotsam')
        coll2 = Collection.objects.create(name='Jetsam')
        digwork.collections.add(coll1)
        digwork.collections.add(coll2)
        index_data = digwork.index_data()
        assert index_data['id'] == digwork.source_id
        assert index_data['srcid'] == digwork.source_id
        assert index_data['item_type'] == 'work'
        assert index_data['title'] == digwork.title
        assert index_data['author'] == digwork.author
        assert index_data['pub_place'] == digwork.pub_place
        assert index_data['pub_date'] == digwork.pub_date
        assert index_data['collections'] == ['Flotsam', 'Jetsam']
        assert index_data['publisher'] == digwork.publisher
        assert index_data['src_url'] == digwork.source_url
        assert not index_data['enumcron']

        # with enumcron
        digwork.enumcron = 'v.7 (1848)'
        assert digwork.index_data()['enumcron'] == digwork.enumcron

    def test_get_absolute_url(self):
        work = DigitizedWork.objects.first()
        assert work.get_absolute_url() == \
            reverse('archive:detail', kwargs={'source_id': work.source_id})


class TestCollection(TestCase):

    fixtures = ['sample_digitized_works']

    def setUp(self):
        # arrange two digital works to use in testing
        self.dig1 = DigitizedWork.objects.get(source_id='chi.78013704')
        self.dig2 = DigitizedWork.objects.get(source_id='chi.13880510')

    def test_str(self):
        collection = Collection(name='Random Assortment')
        assert str(collection) == 'Random Assortment'

    @pytest.mark.usefixtures('solr')
    def test_full_index(self):

        # create collection and associate with digitizedworks
        coll1 = Collection.objects.create(name='Foo')
        self.dig1.collections.add(coll1)
        self.dig2.collections.add(coll1)
        # change the name and reindex all works
        coll1.name = 'Bar'
        coll1.save()
        coll1.full_index()
        sleep(2)
        solr, solr_collection = get_solr_connection()
        # search for old name should yield no results
        res = solr.query(solr_collection, {'q': 'collections_exact:Foo'})
        data = json.loads(res.get_json())
        assert 'response' in data
        assert data['response']['numFound'] == 0
        # search for new name should yield two results
        res = solr.query(solr_collection, {'q': 'collections_exact:Bar'})
        data = json.loads(res.get_json())
        assert 'response' in data
        assert data['response']['numFound'] == 2
        srcids = [doc['srcid'] for doc in data['response']['docs']]
        assert self.dig1.source_id in srcids
        assert self.dig2.source_id in srcids


    @patch('ppa.archive.models.Collection.full_index')
    def test_save(self, mockfullindex):
        # - check flow control on full_index
        # simple save, no previous pk, should simply save
        # in all three cases, the super models.Model save method should be called
        # implicit save in create
        coll1 = Collection.objects.create(name='Foo')
        assert not mockfullindex.called
        # no change to name, mockfulldindex not called
        coll1.save()
        assert not mockfullindex.called
        # change to name, full_index should have been called
        coll1.name = 'Bar'
        coll1.save()
        assert mockfullindex.called

        # set name back
        coll1.name = 'Foo'
        coll1.save()

        # - now check flow control on calls to super method of models.Model
        # have to manually modify pk to force flow control
        with patch('ppa.archive.models.models.Model.save') as mocksuper:
            # each iteration in each state of pk and name should call super
            # one time
            with patch('ppa.archive.models.Collection.objects.get') as mockget:
            # Fully mock out get to avoid problems with travis-ci
                # new save
                coll1.pk = None
                coll1.save()
                # mock full index was called twice in the previous code
                # with two name changes
                assert mockfullindex.call_count == 2
                assert mocksuper.call_count == 1
                # previously saved, no name change
                coll1.pk = 1
                mockget.return_value = coll1
                coll1.save()
                # index call count does not increase
                assert mockfullindex.call_count == 2
                assert mocksuper.call_count == 2
                # previously saved, name change
                # call count should increase, as does full index
                mockget.return_value = Collection(pk=1, name='Bar')
                coll1.save()
                assert mockfullindex.call_count == 3
                assert mocksuper.call_count == 3
