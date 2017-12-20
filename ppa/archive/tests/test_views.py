from django.test import TestCase
from django.urls import reverse
import pytest

from ppa.archive.models import DigitizedWork, Collection


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

        # nothing indexed - should not error
        response = self.client.get(url)
        assert response.status_code == 200
        self.assertContains(response, 'No matching items')


class TestCollectionListView(TestCase):

    def setUp(self):
        '''Create some collections'''
        self.coll1 = Collection.objects.create(name='Random Grabbag')
        self.coll2 = Collection.objects.create(name='Foo through Time')

    def test_context(self):
        '''Check that the context is as expected'''
        collection_list = reverse('archive:list-collections')
        response = self.client.get(collection_list)

        # there should be an object_list in context
        assert 'object_list' in response.context
        # it should be len 2
        assert len(response.context['object_list']) == 2
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
            response, '<ul>',
            msg_prefix='should contain a complete <ul> element', count=2
        )
        self.assertContains(
            response, '<li>',
            msg_prefix='should contain two complete <li> elements', count=4
        )
        self.assertContains(
            response, 'Random Grabbag',
            msg_prefix='should list a collection called Random Grabbag'
        )
        self.assertContains(
            response, 'Foo through Time',
            msg_prefix='should list a collection called Foo through Time'
        )
