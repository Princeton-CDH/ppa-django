import csv
from datetime import date
from io import StringIO
import re
from time import sleep

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now
import pytest

from ppa.archive.models import DigitizedWork, Collection
from ppa.archive.solr import get_solr_connection
from ppa.archive.views import DigitizedWorkCSV


class TestArchiveViews(TestCase):
    fixtures = ['sample_digitized_works']

    def setUp(self):
        self.admin_pass = 'password'
        self.admin_user = get_user_model().objects.create_superuser(
            'admin', 'admin@example.com', self.admin_pass)

    def test_digitizedwork_detailview(self):
        # get a work and its detail page to test with
        dial = DigitizedWork.objects.get(source_id='chi.78013704')
        url = reverse('archive:detail', kwargs={'source_id': dial.source_id})

        # get the detail view page and check that the response is 200
        response = self.client.get(url)
        assert response.status_code == 200

        # now check that the right template is used
        assert 'archive/digitizedwork_detail.html' in \
            [template.name for template in response.templates]

        # check that the appropriate item is in context
        assert 'object' in response.context
        assert response.context['object'] == dial

        # get a work and its detail page to test with
        # wintry = DigitizedWork.objects.get(source_id='chi.13880510')
        # url = reverse('archive:detail', kwargs={'source_id': wintry.source_id})


        # - check that the information we expect is displayed
        # TODO: Make these HTML when the page is styled
        # hathitrust ID
        self.assertContains(
            response, dial.title, count=2,
            msg_prefix='Missing two instance of object.title'
        )
        self.assertContains(
            response, dial.source_id,
            msg_prefix='Missing HathiTrust ID (source_id)'
        )
        self.assertContains(
            response, dial.source_url,
            msg_prefix='Missing source_url'
        )
        self.assertContains(
            response, dial.enumcron,
            msg_prefix='Missing volume/chronology (enumcron)'
        )
        self.assertContains(
            response, dial.author,
            msg_prefix='Missing author'
        )
        self.assertContains(
            response, dial.pub_place,
            msg_prefix='Missing place of publication (pub_place)'
        )
        self.assertContains(
            response, dial.publisher,
            msg_prefix='Missing publisher'
        )
        self.assertContains(
            response, dial.pub_date,
            msg_prefix='Missing publication date (pub_date)'
        )
        self.assertContains(
            response, dial.added.strftime("%d %b %Y"),
            msg_prefix='Missing added or in wrong format (d M Y in filter)'
        )
        self.assertContains(
            response, dial.updated.strftime("%d %b %Y"),
            msg_prefix='Missing updated or in wrong format (d M Y in filter)'
        )

    @pytest.mark.usefixtures("solr")
    def test_digitizedwork_listview(self):
        url = reverse('archive:list')

        # sample page content associated with one of the fixture works
        sample_page_content = [
            'something about winter and wintry and wintriness',
            'something else delightful',
            'an alternate thing with words like blood and bone not in the title'
        ]
        htid = 'chi.13880510'
        solr_page_docs = [
            {'content': content, 'order': i, 'item_type': 'page',
             'srcid': htid, 'id': '%s.%s' % (htid, i)}
            for i, content in enumerate(sample_page_content)]
        # add a collection to use in testing the view
        collection = Collection.objects.create(name='Test Collection')
        digitized_works = DigitizedWork.objects.all()
        self.wintry = digitized_works.filter(title__icontains='Wintry')[0]
        self.wintry.collections.add(collection)
        solr_work_docs = [digwork.index_data() for digwork in digitized_works]
        solr, solr_collection = get_solr_connection()
        index_data = solr_work_docs + solr_page_docs
        solr.index(solr_collection, index_data, params={"commitWithin": 100})
        sleep(2)

        # no query - should find all
        response = self.client.get(url)
        assert response.status_code == 200
        self.assertContains(response, '%d digitized works' % len(digitized_works))
        self.assertContains(response, 'results sorted by title')
        assert response.context['sort'] == 'title'

        for digwork in digitized_works:
            # basic metadata for each work
            self.assertContains(response, digwork.title)
            self.assertContains(response, digwork.source_id)
            self.assertContains(response, digwork.author)
            self.assertContains(response, digwork.enumcron)
            self.assertContains(response, digwork.publisher)
            self.assertContains(response, digwork.pub_place)
            # link to detail page
            self.assertContains(response, digwork.get_absolute_url())

        # search term in title
        response = self.client.get(url, {'query': 'wintry'})
        # relevance sort for keyword search
        assert response.context['sort'] == 'relevance'
        wintry = self.wintry
        self.assertContains(response, '1 digitized work;')
        self.assertContains(response, 'results sorted by relevance')
        self.assertContains(response, wintry.source_id)

        # match in page content but not in book metadata should pull back title
        response = self.client.get(url, {'query': 'blood'})
        self.assertContains(response, '1 digitized work;')
        self.assertContains(response, wintry.source_id)
        self.assertContains(response, wintry.title)

        # search text in author name
        response = self.client.get(url, {'query': 'Robert Bridges'})
        self.assertContains(response, wintry.source_id)

        # search text in publisher name
        response = self.client.get(url, {'query': 'McClurg'})
        for digwork in DigitizedWork.objects.filter(publisher__icontains='mcclurg'):
            self.assertContains(response, digwork.source_id)

        # search text in publication place - matches wintry
        response = self.client.get(url, {'query': 'Oxford'})
        self.assertContains(response, wintry.source_id)

        # exact phrase
        response = self.client.get(url, {'query': '"wintry delights"'})
        self.assertContains(response, '1 digitized work;')
        self.assertContains(response, wintry.source_id)

        # boolean
        response = self.client.get(url, {'query': 'blood AND bone AND alternate'})
        self.assertContains(response, '1 digitized work;')
        self.assertContains(response, wintry.source_id)
        response = self.client.get(url, {'query': 'blood NOT bone'})
        self.assertContains(response, 'No matching items')

        # bad syntax
        response = self.client.get(url, {'query': '"incomplete phrase'})
        self.assertContains(response, 'Unable to parse search query')

        # collection search
        response = self.client.get(url, {'query': 'collections_exact:"Test Collection"'})
        res = response.render()
        print(res.content)
        self.assertContains(response, '1 digitized work;')
        self.assertContains(response, wintry.source_id)

        # nothing indexed - should not error
        solr.delete_doc_by_query(solr_collection, '*:*', params={"commitWithin": 100})
        sleep(2)
        response = self.client.get(url)
        assert response.status_code == 200
        self.assertContains(response, 'No matching items')

    def test_digitizedwork_csv(self):
        # get the csv export and inspect the response
        response = self.client.get(reverse('archive:csv'))
        assert response.status_code == 200
        assert response['content-type'] == 'text/csv'
        content_disposition = response['content-disposition']
        assert content_disposition.startswith('attachment; filename="')
        assert 'ppa-digitizedworks-' in content_disposition
        assert content_disposition.endswith('.csv"')
        assert now().strftime('%Y%m%d') in content_disposition
        assert re.search(r'\d{8}T\d{2}:\d{2}:\d{2}', content_disposition)

        # read content as csv and inspect
        csvreader = csv.reader(StringIO(response.content.decode()))
        rows = [row for row in csvreader]
        digworks = DigitizedWork.objects.order_by('id').all()
        # check for header row
        assert rows[0] == DigitizedWorkCSV.header_row
        # check for expected number of records - header + one row for each work
        assert len(rows) == digworks.count() + 1
        # check expected data in CSV output
        for digwork, digwork_data in zip(digworks, rows[1:]):
            assert digwork.source_id in digwork_data
            assert digwork.title in digwork_data
            assert digwork.author in digwork_data
            assert digwork.pub_date in digwork_data
            assert digwork.pub_place in digwork_data
            assert digwork.publisher in digwork_data
            assert digwork.publisher in digwork_data
            assert digwork.enumcron in digwork_data
            assert ';'.join([coll.name for coll in digwork.collections.all()]) \
                in digwork_data

    def test_digitizedwork_admin_changelist(self):
        # log in as admin to access admin site views
        self.client.login(username=self.admin_user.username,
            password=self.admin_pass)
        # get digitized work change list
        response = self.client.get(reverse('admin:archive_digitizedwork_changelist'))
        self.assertContains(response, reverse('archive:csv'),
            msg_prefix='digitized work change list should include CSV download link')
        self.assertContains(response, 'Download as CSV',
            msg_prefix='digitized work change list should include CSV download button')

        # link should not be on other change lists
        response = self.client.get(reverse('admin:auth_user_changelist'))
        self.assertNotContains(response, reverse('archive:csv'),
            msg_prefix='CSV download link should only be on digitized work list')



class TestCollectionListView(TestCase):

    def setUp(self):
        '''Create some collections'''
        self.coll1 = Collection.objects.create(name='Random Grabbag')
        self.coll2 = Collection.objects.create(
            name='Foo through Time',
            description="A <em>very</em> useful collection."
        )

    def test_context(self):
        '''Check that the context is as expected'''
        collection_list = reverse('archive:list-collections')
        response = self.client.get(collection_list)

        # it should have both collections that exist in it
        assert self.coll1 in response.context['object_list']
        assert self.coll2 in response.context['object_list']

    def test_template(self):
        '''Check that the template is rendering as expected'''
        collection_list = reverse('archive:list-collections')
        response = self.client.get(collection_list)
        # - basic checks right templates
        self.assertTemplateUsed(response, 'base.html')
        self.assertTemplateUsed(response, 'archive/list_collections.html')
        # - detailed checks of template
        self.assertContains(
        response, 'Random Grabbag',
        msg_prefix='should list a collection called Random Grabbag'
        )
        self.assertContains(
            response, 'Foo through Time',
            msg_prefix='should list a collection called Foo through Time'
        )
        self.assertContains(
            response, '<em>very</em>', html=True,
            msg_prefix='should render the description with HTML intact.'
        )
