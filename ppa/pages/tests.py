from wagtail.core.models import Page
from wagtail.tests.utils import WagtailPageTests
from wagtail.tests.utils.form_data import nested_form_data, streamfield


from ppa.pages.models import HomePage, ContentPage
from ppa.editorial.models import EditorialIndexPage


class TestHomePage(WagtailPageTests):

    # NOTE: can't check assertCanCreate since it requires
    # a root page

    def test_parent_pages(self):
        self.assertAllowedParentPageTypes(
            HomePage, [])

    def test_subpages(self):
        self.assertAllowedSubpageTypes(
            HomePage, [ContentPage, EditorialIndexPage, Page])


class TestContentPage(WagtailPageTests):
    fixtures = ['wagtail_pages']

    def test_can_create(self):
        self.assertCanCreateAt(HomePage, ContentPage)
        root = HomePage.objects.first()
        self.assertCanCreate(root, ContentPage, nested_form_data({
            'title': 'About of the PPA',
            'slug': 'about',
            'body': streamfield([
                ('text', 'how the ppa came to be...'),
            ])
        }))

    def test_parent_pages(self):
        self.assertAllowedParentPageTypes(
            ContentPage, [HomePage, ContentPage, Page])

    def test_subpages(self):
        self.assertAllowedSubpageTypes(
            ContentPage, [ContentPage, Page])
