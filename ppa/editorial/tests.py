from datetime import date

from wagtail.tests.utils import WagtailPageTests
from wagtail.tests.utils.form_data import nested_form_data, \
    streamfield, rich_text

from ppa.pages.models import HomePage
from ppa.editorial.models import EditorialIndexPage, EditorialPage


class TestEditorialIndexPage(WagtailPageTests):
    fixtures = ['wagtail_pages']

    def test_parent_pages(self):
        self.assertAllowedParentPageTypes(
            EditorialIndexPage, [HomePage])

    def test_subpages(self):
        self.assertAllowedSubpageTypes(
            EditorialIndexPage, [EditorialPage])

    def test_can_create(self):
        self.assertCanCreateAt(HomePage, EditorialIndexPage)
        root = HomePage.objects.first()
        self.assertCanCreate(root, EditorialIndexPage, nested_form_data({
            'title': 'Editorialization',
            'slug': 'ed',
            'intro': rich_text('about these essays'),
        }))


class TestEditorialPage(WagtailPageTests):
    fixtures = ['wagtail_pages']

    def test_parent_pages(self):
        self.assertAllowedParentPageTypes(
            EditorialPage, [EditorialIndexPage])

    def test_subpages(self):
        self.assertAllowedSubpageTypes(EditorialPage, [])

    def test_can_create(self):
        self.assertCanCreateAt(EditorialIndexPage, EditorialPage)
        parent = EditorialIndexPage.objects.first()
        self.assertCanCreate(parent, EditorialPage, nested_form_data({
            'title': 'Essay',
            'slug': 'essay',
            'date': date.today(),
            'body': streamfield([
                ('paragraph', rich_text('some analysis'))
            ])
        }))
