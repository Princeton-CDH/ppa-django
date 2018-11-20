from datetime import date

from django.http import Http404
from wagtail.core.url_routing import RouteResult
from wagtail.tests.utils import WagtailPageTests
from wagtail.tests.utils.form_data import nested_form_data, \
    streamfield, rich_text
import pytest

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

    def test_route(self):
        index_page = EditorialIndexPage.objects.first()
        # no path components - should serve index page
        response = index_page.route({}, [])
        assert isinstance(response, RouteResult)
        assert response.page == index_page

        # not enough path components should 404
        with pytest.raises(Http404):
            index_page.route({}, ['2018'])
        with pytest.raises(Http404):
            index_page.route({}, ['2018', '11'])

        # non-numeric year/month should 404
        with pytest.raises(Http404):
            index_page.route({}, ['two'])
        with pytest.raises(Http404):
            index_page.route({}, ['2018', 'eleven'])

        # non-existent slug should 404
        with pytest.raises(Http404):
            index_page.route({}, ['2018', '11', 'first-post'])

        # test with actual editorial page
        editorial_page = EditorialPage.objects.first()
        # get the last three pieces of the editorial page url
        path_components = editorial_page.url_path.strip('/').split('/')[-3:]
        response = index_page.route({}, path_components)
        assert response.page == editorial_page


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

    def test_set_url_path(self):
        index_page = EditorialIndexPage.objects.first()
        editorial_page = EditorialPage.objects.first()

        # test existing url path for published page from fixture
        url_path = editorial_page.set_url_path(index_page)
        assert url_path.startswith(index_page.url_path)
        assert url_path.endswith('{}/'.format(editorial_page.slug))
        assert editorial_page.first_published_at.strftime('/%Y/%m/') in url_path

        # no parent
        assert editorial_page.set_url_path(None) == '/'

        # no published date (i.e. draft post); should use current date
        editorial_page.first_published_at = None
        url_path = editorial_page.set_url_path(index_page)
        assert date.today().strftime('/%Y/%m/') in url_path

