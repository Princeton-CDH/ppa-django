import csv
from io import StringIO
import operator
import re
from time import sleep
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.timezone import now
import pytest
from SolrClient.exceptions import SolrError

from ppa.archive.forms import SearchForm
from ppa.archive.models import DigitizedWork, Collection
from ppa.archive.solr import get_solr_connection, PagedSolrQuery
from ppa.archive.views import DigitizedWorkCSV, DigitizedWorkListView, IndexView
from ppa.archive.templatetags.ppa_tags import page_image_url

class TestArchiveViews(TestCase):
    fixtures = ['sample_digitized_works']

    def setUp(self):
        self.admin_pass = 'password'
        self.admin_user = get_user_model().objects.create_superuser(
            'admin', 'admin@example.com', self.admin_pass)

    @pytest.mark.usefixtures("solr")
    def test_digitizedwork_detailview(self):
        # get a work and its detail page to test with
        dial = DigitizedWork.objects.get(source_id='chi.78013704')
        url = reverse('archive:detail', kwargs={'source_id': dial.source_id})

        # get the detail view page and check that the response is 200
        response = self.client.get(url)
        assert response.status_code == 200
        # no keyword search so no note about that
        # no page_obj or search results reflected
        assert 'page_obj' not in response.context
        self.assertNotContains(response, 'No keyword results.')

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
            response, dial.title,
            msg_prefix='Missing title'
        )
        self.assertContains(
            response, dial.source_id,
            msg_prefix='Missing HathiTrust ID (source_id)'
        )
        self.assertContains(
            response, dial.source_url,
            msg_prefix='Missing source_url'
        )
        # self.assertContains(  # disabled for now since it's not in design spec
        #     response, dial.enumcron,
        #     msg_prefix='Missing volume/chronology (enumcron)'
        # )
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
        # only displaying these if logged in currently
        #
        # self.assertContains(
        #     response, dial.added.strftime("%d %b %Y"),
        #     msg_prefix='Missing added or in wrong format (d M Y in filter)'
        # )
        # self.assertContains(
        #     response, dial.updated.strftime("%d %b %Y"),
        #     msg_prefix='Missing updated or in wrong format (d M Y in filter)'
        # )

        # unapi server link present
        self.assertContains(
            response, '''<link rel="unapi-server" type="application/xml"
            title="unAPI" href="%s" />''' % reverse('unapi'),
            msg_prefix='unapi server link should be set', html=True)
        # unapi id present
        self.assertContains(
            response,
            '<abbr class="unapi-id" title="%s"></abbr>' % dial.source_id,
            msg_prefix='unapi id should be embedded for each work')


    @pytest.mark.usefixtures("solr")
    def test_digitizedwork_detailview_query(self):
        '''test digitized work detail page with search query'''

        # get a work and its detail page to test with
        dial = DigitizedWork.objects.get(source_id='chi.78013704')
        url = reverse('archive:detail', kwargs={'source_id': dial.source_id})

        # make some sample page content
        # sample page content associated with one of the fixture works
        sample_page_content = [
            'something about dials and clocks',
            'knobs and buttons',
        ]
        htid = 'chi.78013704'
        solr_page_docs = [
            {'content': content, 'order': i, 'item_type': 'page',
             'srcid': htid, 'id': '%s.%s' % (htid, i)}
             for i, content in enumerate(sample_page_content)]
        dial = DigitizedWork.objects.get(source_id='chi.78013704')
        solr_work_docs = [dial.index_data()]
        solr, solr_collection = get_solr_connection()
        index_data = solr_work_docs + solr_page_docs
        solr.index(solr_collection, index_data, params={"commitWithin": 100})
        sleep(2)

        # search should include query in the context and a PageSolrQuery

        # search with no matches - test empty search result
        response = self.client.get(url, {'query': 'thermodynamics'})
        assert response.status_code == 200
        # query string passsed into context for form
        assert 'query' in response.context
        assert response.context['query'] == 'thermodynamics'
        # solr highlight results in query
        assert 'page_highlights' in response.context
        # should be an empty dict
        assert response.context['page_highlights'] == {}
        # assert solr result in query
        assert 'solr_results' in response.context
        # should be an empty list
        assert response.context['solr_results'] == []

        # test with a word that will produce some snippets
        response = self.client.get(url, {'query': 'knobs'})
        assert response.status_code == 200
        # paginator should be in context
        assert 'page_obj' in response.context
        # it should be one (because we have one result)
        assert response.context['page_obj'].number == 1
        # it should have an object list equal in length to the page solr query
        assert len(response.context['page_obj'].object_list) == \
            len(response.context['solr_results'])
        # get the solr results (should be one)
        result = response.context['solr_results'][0]
        # grab the highlight object that's rendered with our one match
        highlights = response.context['page_highlights'][result['id']]
        # template has the expected information rendered
        self.assertContains(response, highlights['content'][0])
        # image url should appear twice for src and srcset
        self.assertContains(
            response,
            page_image_url(result['srcid'], result['order'], 180),
            count=1
        )
        self.assertContains(
            response,
            page_image_url(result['srcid'], result['order'], 360),
            count=1
        )
        self.assertContains(response, '1 occurrence')

        # bad syntax
        response = self.client.get(url, {'query': '"incomplete phrase'})
        self.assertContains(response, 'Unable to parse search query')

        # test raising a generic solr error
        with patch('ppa.archive.views.PagedSolrQuery') as mockpsq:
            mockpsq.return_value.get_results.side_effect = SolrError
            # count needed for paginator
            mockpsq.return_value.count = 0
            response = self.client.get(url, {'query': 'knobs'})
            self.assertContains(response, 'Something went wrong.')

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
        wintry = digitized_works.filter(title__icontains='Wintry')[0]
        wintry.collections.add(collection)
        solr_work_docs = [digwork.index_data() for digwork in digitized_works]
        solr, solr_collection = get_solr_connection()
        index_data = solr_work_docs + solr_page_docs
        solr.index(solr_collection, index_data, params={"commitWithin": 100})
        sleep(2)

        # no query - should find all
        response = self.client.get(url)
        assert response.status_code == 200
        self.assertContains(response, '%d digitized works' % len(digitized_works))
        assert response.context['sort'] == 'Title A-Z'
        self.assertContains(response, '<p class="result-number">1</p>',
            msg_prefix='results have numbers')
        self.assertContains(response, '<p class="result-number">2</p>',
            msg_prefix='results have multiple numbers')

        # unapi server link present
        self.assertContains(
            response, '''<link rel="unapi-server" type="application/xml"
            title="unAPI" href="%s" />''' % reverse('unapi'),
            msg_prefix='unapi server link should be set', html=True)

        # search form should be set in context for display
        assert isinstance(response.context['search_form'], SearchForm)
        # page group details from expanded part of collapsed query
        assert 'page_groups' in response.context
        # facet range information from publication date range facet
        assert 'facet_ranges' in response.context

        for digwork in digitized_works:
            # basic metadata for each work
            self.assertContains(response, digwork.title)
            self.assertContains(response, digwork.source_id)
            self.assertContains(response, digwork.author)
            self.assertContains(response, digwork.enumcron)
            self.assertContains(response, digwork.publisher)
            self.assertContains(response, digwork.pub_place)
            self.assertContains(response, digwork.pub_date)
            # link to detail page
            self.assertContains(response, digwork.get_absolute_url())
            # unapi identifier for each work
            self.assertContains(
                response,
                '<abbr class="unapi-id" title="%s"></abbr>' % digwork.source_id,
                msg_prefix='unapi id should be embedded for each work')

        # no page images or highlights displayed without search term
        self.assertNotContains(
            response, 'babel.hathitrust.org/cgi/imgsrv/image',
            msg_prefix='no page images displayed without keyword search')

        # search term in title
        response = self.client.get(url, {'query': 'wintry'})
        # relevance sort for keyword search
        assert response.context['sort'] == 'Title A-Z'
        assert len(response.context['object_list']) == 1
        self.assertContains(response, '1 digitized work')
        self.assertContains(response, wintry.source_id)
        # page image & text highlight displayed for matching page
        self.assertContains(
            response,
            'babel.hathitrust.org/cgi/imgsrv/image?id=%s;seq=0' % htid,
            msg_prefix='page image displayed for matching pages on keyword search')
        self.assertContains(
            response, 'winter and <em>wintry</em> and',
            msg_prefix='highlight snippet from page content displayed')

        # page image and text highlight should still display with year filter
        response = self.client.get(url, {'query': 'wintry', 'pub_date_0': 1800})
        assert response.context['page_highlights']
        self.assertContains(
            response, 'winter and <em>wintry</em> and',
            msg_prefix='highlight snippet from page content displayed')
        self.assertContains(
            response,
            'babel.hathitrust.org/cgi/imgsrv/image?id=%s;seq=0' % htid,
            msg_prefix='page image displayed for matching pages on keyword search')
        self.assertContains(
            response, 'winter and <em>wintry</em> and',
            msg_prefix='highlight snippet from page content displayed')


        # match in page content but not in book metadata should pull back title
        response = self.client.get(url, {'query': 'blood'})
        self.assertContains(response, '1 digitized work')
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
        self.assertContains(response, '1 digitized work')
        self.assertContains(response, wintry.source_id)

        # boolean
        response = self.client.get(url, {'query': 'blood AND bone AND alternate'})
        self.assertContains(response, '1 digitized work')
        self.assertContains(response, wintry.source_id)
        response = self.client.get(url, {'query': 'blood NOT bone'})
        self.assertContains(response, 'No matching works.')

        # bad syntax
        response = self.client.get(url, {'query': '"incomplete phrase'})
        self.assertContains(response, 'Unable to parse search query')

        # add a sort term - pub date
        response = self.client.get(url, {'query': '', 'sort': 'pub_date_asc'})
        # explicitly sort by pub_date manually
        sorted_object_list = sorted(response.context['object_list'],
                                    key=operator.itemgetter('pub_date'))
        # the two context lists should match exactly
        assert sorted_object_list == response.context['object_list']
        # human readable value should be set in context using the value
        # of SearchForm.SORT_CHOICES
        assert response.context['sort'] == \
            dict(SearchForm.SORT_CHOICES)['pub_date_asc']
        # test sort date in reverse
        response = self.client.get(url, {'query': '', 'sort': 'pub_date_desc'})
        # explicitly sort by pub_date manually in descending order
        sorted_object_list = sorted(response.context['object_list'],
                                    key=operator.itemgetter('pub_date'),
                                    reverse=True)
        # the two context lists should match exactly
        assert sorted_object_list == response.context['object_list']
        # human readable value should be set in context using the value
        # of SearchForm.SORT_CHOICES
        assert response.context['sort'] == \
            dict(SearchForm.SORT_CHOICES)['pub_date_desc']
        # one last test using title
        response = self.client.get(url, {'query': '', 'sort': 'title_asc'})
        sorted_object_list = sorted(response.context['object_list'],
                                    key=operator.itemgetter('title_exact'))
        # the two context lists should match exactly
        assert sorted_object_list == response.context['object_list']
        # human readable value should be set in context using the value
        # of SearchForm.SORT_CHOICES
        assert response.context['sort'] == \
            dict(SearchForm.SORT_CHOICES)['title_asc']

        # - check that a query allows relevance as sort order toggle in form
        response = self.client.get(url, {'query': 'foo', 'sort': 'title_asc'})
        self.assertContains(
            response,
            '<input type="radio" name="sort" value="relevance" id="id_sort_0" />',
            html=True
        )
        # check that a search that does not have a query disables
        # relevance as a sort order option
        response = self.client.get(url, {'sort': 'title_asc'})
        self.assertContains(
            response,
            '<input type="radio" name="sort" value="relevance" id="id_sort_0" disabled="disabled" />',
            html=True
        )
        # collection search
        response = self.client.get(url, {'query': 'collections_exact:"Test Collection"'})
        assert len(response.context['object_list']) == 1
        self.assertContains(response, wintry.source_id)

        # basic date range request
        response = self.client.get(url, {'pub_date_0': 1900, 'pub_date_1': 1922})
        # in fixture data, only wintry is after 1900
        assert len(response.context['object_list']) == 1
        self.assertContains(response, wintry.source_id)

        # invalid date range request / invalid form - not an exception
        response = self.client.get(url, {'pub_date_0': 1900, 'pub_date_1': 1800})
        assert not response.context['object_list'].count()
        self.assertContains(response, 'Invalid range')

        # nothing indexed - should not error
        solr.delete_doc_by_query(solr_collection, '*:*', params={"commitWithin": 100})
        sleep(2)
        response = self.client.get(url)
        assert response.status_code == 200
        self.assertContains(response, 'No matching works.')

        # simulate solr exception (other than query syntax)
        with patch('ppa.archive.views.PagedSolrQuery') as mockpsq:
            mockpsq.return_value.get_expanded.side_effect = SolrError
            # count needed for paginator
            mockpsq.return_value.count = 0
            response = self.client.get(url, {'query': 'something'})
            self.assertContains(response, 'Something went wrong.')

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
            assert str(digwork.pub_date) in digwork_data
            assert digwork.pub_place in digwork_data
            assert digwork.publisher in digwork_data
            assert digwork.publisher in digwork_data
            assert digwork.enumcron in digwork_data
            assert ';'.join([coll.name for coll in digwork.collections.all()]) \
                in digwork_data
            assert '%d' % digwork.page_count in digwork_data
            assert '%s' % digwork.added in digwork_data
            assert '%s' % digwork.updated in digwork_data

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

    @pytest.mark.usefixtures("solr")
    def test_collection_list(self):
        # Create test collections to display
        coll1 = Collection.objects.create(name='Random Grabbag')
        coll2 = Collection.objects.create(
            name='Foo through Time',
            description="A <em>very</em> useful collection."
        )

        # Check that the context is set as expected
        collection_list = reverse('archive:list-collections')
        response = self.client.get(collection_list)
        # it should have both collections that exist in it
        assert coll1 in response.context['object_list']
        assert coll2 in response.context['object_list']

        # Check that the template is rendering as expected
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

        ## test collection stats from Solr

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

        response = self.client.get(collection_list)
        # stats set properly in context
        assert 'stats' in response.context
        assert response.context['stats'][coll1.name]['count'] == digworks.count()
        assert response.context['stats'][coll1.name]['dates'] == '1880–1903'
        assert response.context['stats'][coll2.name]['count'] == 1
        assert response.context['stats'][coll2.name]['dates'] == '1903'
        # stats displayed on template
        self.assertContains(response, '%d digitized works' % digworks.count())
        self.assertContains(response, '1 digitized work')
        self.assertNotContains(response, '1 digitized works')
        self.assertContains(response, '1880–1903')
        self.assertContains(response, '1903')


class TestAddToCollection(TestCase):

    fixtures = ['sample_digitized_works']

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='test',
                                                         password='secret')
        self.user.save()

        get_user_model().objects.create_superuser(
            username='super', password='secret', email='foo@bar.com'
        )

    def test_permissions(self):
        # - anonymous login is redirected to sign in
        bulk_add = reverse('archive:add-to-collection')
        response = self.client.get(bulk_add)
        assert response.status_code == 302
        # - so is a user without staff permissions
        self.client.login(username='test', password='secret')
        response = self.client.get(bulk_add)
        assert response.status_code == 302
        self.user.is_staff = True
        self.user.save()
        # a logged in staff user is not redirected
        response = self.client.get(bulk_add)
        assert response.status_code == 200

    def test_get(self):

        self.client.login(username='super', password='secret')

        # - a get to the view with ids should return a message to use
        # the admin interface and not enable the form for submission
        bulk_add = reverse('archive:add-to-collection')
        response = self.client.get(bulk_add)
        self.assertContains(response,
            '<h1>Add Digitized Works to Collections</h1>', html=True)
        self.assertContains(
            response,
            'Please select digitized works from the admin interface.'
        )
        # sending a set of pks that don't exist should produce the same result
        session = self.client.session
        session['collection-add-ids'] = [100, 101]
        session.save()
        response = self.client.get(bulk_add)
        # check that the session var has been set to an empy list
        assert self.client.session.get('collection-add-ids') == []
        self.assertContains(
            response,
            'Please select digitized works from the admin interface.'
        )
        # create a collection and send valid pks
        coll1 = Collection.objects.create(name='Random Grabbag')
        session['collection-add-ids'] = [1, 2]
        session.save()
        response = self.client.get(bulk_add)
        # check html=False so we can look for just the opening tag of the form
        # block (html expects all the content between the closing tag too!)
        self.assertContains(
            response,
            '<form method="post"',
        )
        self.assertContains(
            response,
            '<option value="%d">Random Grabbag</option>' % coll1.id,
            html=True
        )

    @patch('ppa.archive.views.get_solr_connection')
    def test_post(self, mockgetsolr):

        mocksolr = Mock()
        mockcollection = Mock()
        mockgetsolr.return_value = mocksolr, mockcollection

        self.client.login(username='super', password='secret')

        # - check that a post to the bulk-add route with valid pks
        # adds them to the appropriate collection
        # make a collection
        coll1 = Collection.objects.create(name='Random Grabbag')
        digworks = DigitizedWork.objects.order_by('id')[0:2]
        pks = list(digworks.values_list('id', flat=True))
        bulk_add = reverse('archive:add-to-collection')
        session = self.client.session
        session['collection-add-ids'] = pks
        session.save()

        # post to the add to collection url
        res = self.client.post(bulk_add, {'collections': coll1.pk})
        # redirects to the admin archive change list by default without filters
        # since none are set
        assert res.status_code == 302
        assert res.url == \
            reverse('admin:archive_digitizedwork_changelist')
        # digitized works with pks 1,2 are added to the collection
        digworks = DigitizedWork.objects\
            .filter(collections__pk=coll1.pk).order_by('id')
        assert digworks.count() == 2
        assert list(digworks.values_list('id', flat=True)) == \
            session['collection-add-ids']
        # the session variable is cleared
        assert 'collection-add-ids' not in self.client.session
        # - check that solr indexing was called correctly via mocks
        assert mockgetsolr.called
        solr_docs = [work.index_data() for work in digworks]
        mocksolr.index.assert_called_with(
            mockcollection, solr_docs, params={'commitWithin': 2000}
        )

        # - bulk add should actually add and not reset collections, i.e.
        # those individually added or added in a previous bulk add shouldn't
        # be erased from the collection's digitizedwork_set
        # only set pk 1 in the ids to add
        session['collection-add-ids'] = [digworks[0].pk]
        # also check that filters are preserved
        session['collection-add-filters'] = {'q': 1, 'foo': 'bar'}
        session.save()

        # bulk adding first pk but not the second
        res = self.client.post(bulk_add, {'collections': coll1.pk})
        # redirect as expected and retain querystring
        assert res.status_code == 302
        assert res.url == '%s?%s' % \
            (reverse('admin:archive_digitizedwork_changelist'),
             urlencode(session['collection-add-filters'].items()))
        digworks2 = DigitizedWork.objects\
            .filter(collections__pk=coll1.pk).order_by('id')
        # this will fail if the bulk add removed the previously set two works
        assert digworks2.count() == 2
        # they should also be the same objects as before, i.e. this post request
        # should result in a noop
        assert digworks == digworks

        # - test a dud post (i.e. without a Collection)
        # should redirect with an error
        session['collection-add-ids'] = pks
        session.save()
        response = self.client.post(bulk_add, {'collections': None})
        assert response.status_code == 200
        # check that the error message rendered for a missing Collection
        self.assertContains(
            response,
            '<ul class="errorlist"><li>Please select at least one '
            'Collection</li></ul>',
            html=True
        )
        session['collection-add-ids'] = None
        session.save()
        response = self.client.post(bulk_add, {'collections': coll1.pk})
        # Default message for an unset collection pk list
        self.assertContains(
            response,
            '<p> Please select digitized works from the admin interface. </p>',
            html=True
        )


class TestDigitizedWorkListView(TestCase):

    def test_get_page_highlights(self):

        digworkview = DigitizedWorkListView()

        # no keyword or page groups, no highlights
        assert digworkview.get_page_highlights({}) == {}

        # search term but no page groups
        digworkview.query = 'iambic'
        assert digworkview.get_page_highlights({}) == {}

        # mock PagedSolrQuery to inspect that query is generated properly
        with patch('ppa.archive.views.PagedSolrQuery',
                   spec=PagedSolrQuery) as mockpsq:
            page_groups = {
                'group1': {
                    'docs': [
                        {'id': 'p1a'},
                        {'id': 'p1b'},
                    ]},
                'group2': {
                    'docs': [
                        {'id': 'p2a'},
                        {'id': 'p2b'},
                    ]},
            }

            highlights = digworkview.get_page_highlights(page_groups)
            # inspect the solr call; first arg is a dictionary, no kwargs
            solr_args = mockpsq.call_args[0]
            solr_opts = solr_args[0]
            # highlighting turned on
            assert solr_opts['hl']
            # not testing this as strictly while we play around with it
            # assert solr_opts['hl.snippets'] == 1
            assert solr_opts['hl.fl'] == 'content'
            assert solr_opts['hl.method'] == 'unified'
            # rows should match # of page ids
            assert solr_opts['rows'] == 4
            # query includes keyword search term
            assert 'text:(%s) AND ' % digworkview.query in solr_opts['q']
            # query also inlcudes page ids
            assert ' AND id:("p1a" "p1b" "p2a" "p2b")' in solr_opts['q']

            assert highlights == mockpsq.return_value.get_highlighting()


class TestIndexView(TestCase):

    @pytest.mark.usefixtures("solr")
    def test_get_queryset(self):

        # Create test collections to display
        coll1 = Collection.objects.create(name='Random Grabbag')
        coll2 = Collection.objects.create(
            name='Foo through Time',
            description="A <em>very</em> useful collection."
        )

        # Check that the context is set as expected
        index = reverse('home')
        response = self.client.get(index)
        # it should have both collections that exist in it
        assert coll1 in response.context['object_list']
        assert coll2 in response.context['object_list']

        # Check that the template is rendering as expected
        # - basic checks right templates
        self.assertTemplateUsed(response, 'base.html')
        self.assertTemplateUsed(response, 'site_index.html')
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

        # Add another collection
        coll3 = Collection.objects.create(
            name='Bar through Time',
            description='A somewhat less useful collection.'
        )
        response = self.client.get(index)
        # only two collections should be returned in the response
        assert len(response.context['object_list']) == 2