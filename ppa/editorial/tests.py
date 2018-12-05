from datetime import date

from django.http import Http404
from django.test import TestCase
from wagtail.core.url_routing import RouteResult
from wagtail.core.models import Site
from wagtail.tests.utils import WagtailPageTests
from wagtail.tests.utils.form_data import nested_form_data, \
    streamfield, rich_text
import pytest

from ppa.pages.models import HomePage
from ppa.editorial.models import EditorialIndexPage, EditorialPage
from ppa.pages.models import Person


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
        # test route method directly

        index_page = EditorialIndexPage.objects.first()
        # no path components - should serve index page
        response = index_page.route({}, [])
        assert isinstance(response, RouteResult)
        assert response.page == index_page

        # not enough path components should 404
        with pytest.raises(Http404):
            index_page.route({}, ['2018'])
        with pytest.raises(Http404):
            index_page.route({}, ['2018', '01'])

        # non-numeric year/month should 404
        with pytest.raises(Http404):
            index_page.route({}, ['two'])
        with pytest.raises(Http404):
            index_page.route({}, ['2018', 'one'])

        # non-existent slug should 404
        with pytest.raises(Http404):
            index_page.route({}, ['2018', '01', 'first-post'])

        # test with actual editorial page
        editorial_page = EditorialPage.objects.first()
        # get the last three pieces of the editorial page url
        path_components = editorial_page.url_path.strip('/').split('/')[-3:]
        response = index_page.route({}, path_components)
        assert response.page == editorial_page

    def test_routing(self):
        # test getting urls with django test client

        index_page = EditorialIndexPage.objects.first()
        editorial_page = EditorialPage.objects.first()
        site = Site.objects.first()
        editorial_index_url = index_page.relative_url(site)
        response = self.client.get(editorial_index_url)
        assert response.status_code == 200
        editorial_with_authors = EditorialPage.objects.get(
            title__icontains='Test Page with Authors'
        )
        # basic template/content check
        # NOTE: Should these be refactored into separate template
        # checking test?
        self.assertContains(response, index_page.title)
        self.assertContains(response, editorial_page.title)
        self.assertContains(response, editorial_page.relative_url(site))
        # each should be shown once
        person_a = Person.objects.get(name='Person A')
        person_b = Person.objects.get(name='Person B')
        self.assertContains(response, person_a.name, count=1)
        self.assertContains(response, person_b.name, count=1)
        # each should only show the 'By' and 'On' twice (for two dates)
        self.assertContains(response, 'By', count=1)
        self.assertContains(response, 'On', count=2)
        # the url for person A should not be present to avoid a
        # link within a link
        self.assertNotContains(
            response,
            '<a href="%s"' % person_a.url,
            html=True,
        )
        # the date of the post's publication should be present with slash
        self.assertContains(
            response,
            '/ On %s' % editorial_with_authors
                .first_published_at.strftime('%B %-d, %Y'),
            count=1
            )
        # the date of the post without authors should be present, without slash
        self.assertContains(
            response,
            'On %s' % editorial_page
                .first_published_at.strftime('%B %-d, %Y'),
            count=1
            )

        # year only should 404
        response = self.client.get(editorial_index_url + '2018/')
        assert response.status_code == 404
        # year/month only should 404
        response = self.client.get(editorial_index_url + '2018/01/')
        assert response.status_code == 404
        # non-existent slug should 404
        response = self.client.get(editorial_index_url + '2018/01/not-found/')
        assert response.status_code == 404
        # non-numeric should 404
        response = self.client.get(editorial_index_url + '2018/two/not-found/')
        assert response.status_code == 404

        response = self.client.get(editorial_page.relative_url(site))
        assert response.status_code == 200

        # single-digit month should 404
        response = self.client.get(editorial_page.relative_url(site).replace('/01/', '/1/'))
        assert response.status_code == 404


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
        # first test without authors, since they're optional
        self.assertCanCreate(parent, EditorialPage, nested_form_data({
            'title': 'Essay',
            'slug': 'essay',
            'date': date.today(),
            'body': streamfield([
                ('paragraph', rich_text('some analysis'))
            ]),
            'authors': streamfield([])
        }))

        # now check that this can be done with the person snippet,
        # both with and without url
        foo = Person.objects.create(name='foo', url='http://bar.com/')
        bar = Person.objects.create(name='bar')
        self.assertCanCreate(parent, EditorialPage, nested_form_data({
            'title': 'Essay2',
            'slug': 'essay2',
            'date': date.today(),
            'body': streamfield([
                ('paragraph', rich_text('some analysis'))
            ]),
            'authors': streamfield([
                ('author', foo.pk),
                ('author', bar.pk)
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

    def test_template_rendering(self):
        # For EditorialIndexPage's equivalent, see test_routing
        editorial_page = EditorialPage.objects.get(
            title__icontains='Test Page with Authors'
        )
        site = Site.objects.first()
        editorial_url = editorial_page.relative_url(site)
        response = self.client.get(editorial_url)
        # basic template/content check
        self.assertContains(response, editorial_page.title)
        # each author should be shown once
        person_a = Person.objects.get(name='Person A')
        person_b = Person.objects.get(name='Person B')
        self.assertContains(response, person_a.name, count=1)
        self.assertContains(response, person_b.name, count=1)
        # each should only show the 'By' and 'On' once
        self.assertContains(response, 'By', count=1)
        self.assertContains(response, 'On', count=1)
        # the date of the post's publication should be present with slash
        self.assertContains(
            response,
            '/ On %s' % editorial_page
                .first_published_at.strftime('%B %-d, %Y'),
            count=1
            )
        # the url for person A should be present once
        self.assertContains(response, person_a.url, count=1)
        # check order of authors in the page context
        # should be out of alpha order
        page = response.context['page']
        # authors are stored as values and not as actual links,
        # so without the template tag to unpack the stream data,
        # can check that their value = pk of authors.
        # order as set in the editorial page should be [B is 2, A is 1]
        assert page.authors.stream_data[0]['value'] == 2
        assert page.authors.stream_data[1]['value'] == 1
        # delete them
        editorial_page.authors = None
        editorial_page.save()
        response = self.client.get(editorial_url)
        # each author should be shown once
        self.assertNotContains(response, person_a.name)
        self.assertNotContains(response, person_b.name)
        # each should not show the 'By' and 'On' once with date still
        # the date of the post's publication should be present
        # without slash
        self.assertContains(
            response,
            'On %s' % editorial_page
                .first_published_at.strftime('%B %-d, %Y'),
            count=1
            )


class TestPerson(TestCase):

    def test_str(self):
        p = Person(name='A person')
        assert str(p) == 'A person'
