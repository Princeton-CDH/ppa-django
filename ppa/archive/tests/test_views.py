from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
import pytest

from ppa.archive.models import DigitizedWork


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


class TestDigitizedWorkAutocomplete(TestCase):

    fixtures = ['sample_digitized_works']

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            'foo',
            'foo@bar.com',
            'bar'
        )

    def test_get_queryset_get_result_label(self):
        '''Tests both what is being returned and that it is being returned
           so gets at both get_queryset and get_result_label
        '''
        autocomplete_url = reverse('archive:digitizedwork-autocomplete')

        # - check access control
        # anonymous user should get a redirect to login
        response = self.client.get(autocomplete_url)
        assert response.status_code == 302
        # admin user should be allowed in
        self.client.login(username='foo', password='bar')
        response = self.client.get(autocomplete_url)
        assert response.status_code == 200
        # - test results
        # empty query string should result in all results (three in this case)
        data = response.json()
        assert 'results' in data
        assert len(data['results']) == 3
        # pass a query string along -- should get 1 result
        response = self.client.get(autocomplete_url, {'q': 'wintry'})
        data = response.json()
        assert 'results' in data
        assert len(data['results']) == 1
        # - examine the text of the result for HTML formatting
        assert 'text' in data['results'][0]
        assert data['results'][0]['text'] == \
            '<strong>Now in wintry delights /</strong><br>chi.13880510'
