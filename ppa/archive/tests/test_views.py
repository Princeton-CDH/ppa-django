from django.test import TestCase
from django.urls import reverse

from ppa.archive.models import DigitizedWork


class TestDigitizedWorkDetailView(TestCase):

    fixtures = ['sample_digitized_works']

    def test_get_context(self):

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

    def test_template_rendering(self):
        # get a work and its detail page to test with
        wintry = DigitizedWork.objects.get(source_id='chi.13880510')
        url = reverse('archive:detail', kwargs={'source_id': wintry.source_id})

        # get the detail view page and check that the response is 200
        response = self.client.get(url)
        assert response.status_code == 200

        # - check that the information we expect is displayed
        # TODO: Make these HTML when the page is styled
        # hathitrust ID
        self.assertContains(
            response, wintry.title, count=2,
            msg_prefix='Missing two instance of object.title'
        )
        self.assertContains(
            response, wintry.source_id,
            msg_prefix='Missing HathiTrust ID (source_id)'
        )
        self.assertContains(
            response, wintry.source_url,
            msg_prefix='Missing source_url'
        )
        self.assertContains(
            response, wintry.enumcron,
            msg_prefix='Missing volume/chronology (enumcron)'
        )
        self.assertContains(
            response, wintry.author,
            msg_prefix='Missing author'
        )
        self.assertContains(
            response, wintry.pub_place,
            msg_prefix='Missing place of publication (pub_place)'
        )
        self.assertContains(
            response, wintry.publisher,
            msg_prefix='Missing publisher'
        )
        self.assertContains(
            response, wintry.pub_date,
            msg_prefix='Missing publication date (pub_date)'
        )
        self.assertContains(
            response, wintry.added.strftime("%d Dec %Y"),
            msg_prefix='Missing added or in wrong format (d M Y in filter)'
        )
        self.assertContains(
            response, wintry.updated.strftime("%d Dec %Y"),
            msg_prefix='Missing updated or in wrong format (d M Y in filter)'
        )
