from django.contrib.sites.models import Site
from django.test import TestCase
from wagtail.core.models import Page

from ppa.editorial.models import EditorialIndexPage
from ppa.pages.management.commands import setup_site_pages
from ppa.pages.models import CollectionPage, ContentPage, HomePage


class TestSetupSitePagesCommand(TestCase):
    def setUp(self):
        self.cmd = setup_site_pages.Command()

    def test_create_wagtail_site(self):
        root_page = Page.objects.first()
        # test with existing example.com default site first
        wagtail_site = self.cmd.create_wagtail_site(root_page)

        # port should be inferred when not present in domain
        site = Site.objects.first()
        assert wagtail_site.hostname == site.domain
        assert wagtail_site.port == 80
        assert wagtail_site.site_name == site.name
        assert wagtail_site.root_page == root_page
        assert wagtail_site.is_default_site

        # port should be split out when present
        site.domain = "localhost:8000"
        site.save()
        wagtail_site = self.cmd.create_wagtail_site(root_page)
        assert wagtail_site.hostname == "localhost"
        assert wagtail_site.port == "8000"

    def test_create_pages(self):
        self.cmd.handle()

        # initial welcome to wagtail home page should be gone
        assert not Page.objects.filter(slug="home", title__contains="Welcome").count()

        # should be one of each: home page, editorial index, collection
        for page_type in [HomePage, EditorialIndexPage, CollectionPage]:
            assert page_type.objects.count() == 1

        # one content stub page created based on content page dictionary
        assert ContentPage.objects.count() == len(self.cmd.content_pages)

        home = HomePage.objects.first()
        # preview pages associated
        assert home.page_preview_1
        assert home.page_preview_2

        # running again should not create duplicates
        self.cmd.handle()

        # still only one of each: home page, editorial index, collection
        for page_type in [HomePage, EditorialIndexPage, CollectionPage]:
            assert page_type.objects.count() == 1

        # one content stub page created based on content page dictionary
        assert ContentPage.objects.count() == len(self.cmd.content_pages)
