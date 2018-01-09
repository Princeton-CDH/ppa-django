import json
import os.path
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
        # delete the index that happens as part of save
        solr.delete_doc_by_query(solr_collection, '*')
        solr.commit(solr_collection, openSearcher=True, waitSearcher=True)
        # digwork should be unindexed
        res = solr.query(solr_collection, {'q': '*:*'})
        assert res.get_results_count() == 0
        # reindex to check that the method works on a saved object
        digwork.index()
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

    @pytest.mark.usefixtures('solr')
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


@pytest.mark.usefixtures('solr')
class TestCollection(TestCase):

    fixtures = ['sample_digitized_works']

    def test_str(self):
        collection = Collection(name='Random Assortment')
        assert str(collection) == 'Random Assortment'

    def test_save(self):
        collection = Collection.objects.create(name='Foo')
        digwork = DigitizedWork(source_id='njp.32101013082597')
        digwork.save()
        digwork.collections.add(collection)
        digwork.save()

        solr, solr_collection = get_solr_connection()
        res = solr.query(solr_collection, {'q': 'collections_exact:Foo'})
        assert res.get_results_count() == 1
        assert res.docs[0]['collections_exact'] == ['Foo']
        collection.name = 'Foobar'
        collection.save()
