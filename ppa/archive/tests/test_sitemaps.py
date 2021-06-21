from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from ppa.archive.models import DigitizedWork
from ppa.archive.sitemaps import ArchiveViewsSitemap, DigitizedWorkSitemap


class TestArchiveViewsSitemap(TestCase):
    fixtures = ["sample_digitized_works"]

    def setUp(self):
        self.sitemap = ArchiveViewsSitemap()
        self.latest_digwork = DigitizedWork.objects.order_by("-updated").first()

    def test_items(self):
        items = self.sitemap.items()
        assert "list" in items
        # collection list view no longer in archives (now a wagtail page)
        assert "list-collections" not in items

    def test_location(self):
        assert self.sitemap.location("list") == reverse("archive:list")

    def test_lastmod(self):
        assert self.sitemap.lastmod("list") == self.latest_digwork.updated
        assert self.sitemap.lastmod("list-collection") == self.latest_digwork.updated

    def test_get(self):
        # test that it actually renders, to catch any other problems
        resp = self.client.get("/sitemap-archive.xml")
        assert resp.status_code == 200


class TestDigitizedWorkSitemap(TestCase):
    fixtures = ["sample_digitized_works"]

    def setUp(self):
        self.sitemap = DigitizedWorkSitemap()

    def test_items(self):
        assert list(DigitizedWork.objects.all()) == list(self.sitemap.items())

        # should not include suppressed items
        digwork = DigitizedWork.objects.first()
        digwork.status = DigitizedWork.SUPPRESSED
        # don't actually process the data deletion
        with patch.object(digwork, "hathi") as mock_delete_pairtree_data:
            digwork.save()

        assert digwork not in list(self.sitemap.items())

    def test_lastmod(self):
        digwork = DigitizedWork.objects.first()
        assert self.sitemap.lastmod(digwork) == digwork.updated

    def test_get(self):
        # test that it actually renders, to cactch any other problems
        resp = self.client.get("/sitemap-digitizedworks.xml")
        assert resp.status_code == 200
