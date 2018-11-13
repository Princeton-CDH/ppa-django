from django.test import TestCase
from django.urls import reverse

from ppa.archive.models import DigitizedWork
from ppa.archive.sitemaps import ArchiveViewsSitemap, DigitizedWorkSitemap


class TestArchiveViewsSitemap(TestCase):
    fixtures = ['sample_digitized_works']

    def setUp(self):
        self.sitemap = ArchiveViewsSitemap()
        self.latest_digwork = DigitizedWork.objects.order_by('-updated').first()

    def test_items(self):
        items = self.sitemap.items()
        assert 'list' in items
        assert 'list-collections' in items

    def test_location(self):
        assert self.sitemap.location('list') == reverse('archive:list')

    def test_lastmod(self):
        assert self.sitemap.lastmod('list') == self.latest_digwork.updated
        assert self.sitemap.lastmod('list-collection') \
            == self.latest_digwork.updated


class TestDigitizedWorkSitemap(TestCase):
    fixtures = ['sample_digitized_works']

    def setUp(self):
        self.sitemap = DigitizedWorkSitemap()

    def test_items(self):
        assert list(DigitizedWork.objects.all()) == list(self.sitemap.items())

    def test_lastmod(self):
        digwork = DigitizedWork.objects.first()
        assert self.sitemap.lastmod(digwork) == digwork.updated