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

    def test_get_context(self):
        index_page = EditorialIndexPage.objects.first()
        ed_page = EditorialPage.objects.first()
        context = index_page.get_context({})
        assert 'posts' in context
        assert ed_page in context['posts']

        # set to not published
        ed_page.live = False
        ed_page.save()
        context = index_page.get_context({})
        assert ed_page not in context['posts']

        # TODO: test with multiple, check sort order


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
