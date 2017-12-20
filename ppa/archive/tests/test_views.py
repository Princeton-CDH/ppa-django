from time import sleep

from django.test import TestCase
from django.urls import reverse
import pytest

from ppa.archive.models import DigitizedWork
from ppa.archive.solr import get_solr_connection


class TestArchiveViews(TestCase):

    fixtures = ['sample_digitized_works']

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
            response, dial.added.strftime("%d Dec %Y"),
            msg_prefix='Missing added or in wrong format (d M Y in filter)'
        )
        self.assertContains(
            response, dial.updated.strftime("%d Dec %Y"),
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
        digitized_works = DigitizedWork.objects.all()
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
        wintry = digitized_works.filter(title__contains='Wintry').first()
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
        for digwork in digitized_works.filter(publisher__icontains='mcclurg'):
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

        # nothing indexed - should not error
        solr.delete_doc_by_query(solr_collection, '*:*', params={"commitWithin": 100})
        sleep(2)
        response = self.client.get(url)
        assert response.status_code == 200
        self.assertContains(response, 'No matching items')
