from datetime import date

import pytest
from django.http import Http404
from django.test import TestCase, override_settings
from django.test.client import RequestFactory
from wagtail.models import Site
from wagtail.url_routing import RouteResult
from wagtail.test.utils import WagtailPageTestCase
from wagtail.test.utils.form_data import nested_form_data, rich_text, streamfield
from unittest.mock import patch

from ppa.editorial.models import EditorialIndexPage, EditorialPage, GeneratePdfPanel
from ppa.editorial.wagtail_hooks import editor_js
from ppa.pages.models import HomePage, Person


class TestEditorialIndexPage(WagtailPageTestCase):
    fixtures = ["wagtail_pages"]

    def test_parent_pages(self):
        self.assertAllowedParentPageTypes(EditorialIndexPage, [HomePage])

    def test_subpages(self):
        self.assertAllowedSubpageTypes(EditorialIndexPage, [EditorialPage])

    def test_can_create(self):
        self.assertCanCreateAt(HomePage, EditorialIndexPage)

    def test_get_context(self):
        index_page = EditorialIndexPage.objects.first()
        ed_page = EditorialPage.objects.first()
        context = index_page.get_context({})
        assert "posts" in context
        posts = [post.specific for post in context["posts"]]
        assert ed_page in posts

        # unpublish
        index_page.get_children().all().unpublish()
        context = index_page.get_context({})
        assert ed_page not in context["posts"]

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
            index_page.route({}, ["2018"])
        with pytest.raises(Http404):
            index_page.route({}, ["2018", "01"])

        # non-numeric year/month should 404
        with pytest.raises(Http404):
            index_page.route({}, ["twos"])
        with pytest.raises(Http404):
            index_page.route({}, ["2018", "on"])

        # non-existent slug should 404
        with pytest.raises(Http404):
            index_page.route({}, ["2018", "01", "first-post"])

        # test with actual editorial page
        editorial_page = EditorialPage.objects.first()
        # get the last three pieces of the editorial page url
        path_components = editorial_page.url_path.strip("/").split("/")[-3:]
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

        # year only should 404
        response = self.client.get(editorial_index_url + "2018/")
        assert response.status_code == 404
        # year/month only should 404
        response = self.client.get(editorial_index_url + "2018/01/")
        assert response.status_code == 404
        # non-existent slug should 404
        response = self.client.get(editorial_index_url + "2018/01/not-found/")
        assert response.status_code == 404
        # non-numeric should 404
        response = self.client.get(editorial_index_url + "2018/two/not-found/")
        assert response.status_code == 404

        response = self.client.get(editorial_page.relative_url(site))
        assert response.status_code == 200

        # single-digit month should 404
        response = self.client.get(
            editorial_page.relative_url(site).replace("/01/", "/1/")
        )
        assert response.status_code == 404

    def test_template_rendering(self):
        # basic template/content check
        site = Site.objects.first()
        index_page = EditorialIndexPage.objects.first()
        editorial_page = EditorialPage.objects.first()
        editorial_index_url = index_page.relative_url(site)
        editorial_with_authors = EditorialPage.objects.get(
            title__icontains="Test Page with Authors"
        )
        response = self.client.get(editorial_index_url)
        self.assertContains(response, index_page.title)
        self.assertContains(response, editorial_page.title)
        self.assertContains(response, editorial_page.relative_url(site))
        # each should be shown once
        person_a = Person.objects.get(name="Person A")
        person_b = Person.objects.get(name="Person B")
        self.assertContains(response, person_a.name, count=1)
        self.assertContains(response, person_b.name, count=1)
        # the url for person A should not be present to avoid a
        # link within a link
        self.assertNotContains(
            response,
            '<a href="%s"' % person_a.url,
            html=True,
        )
        # the date of the post's publication should be present in readable form
        self.assertContains(
            response,
            "%s" % editorial_with_authors.first_published_at.strftime("%B %-d, %Y"),
            count=1,
        )
        # present in an attribute in ISO form
        self.assertContains(
            response,
            "%s" % editorial_with_authors.first_published_at.strftime("%Y-%m-%d"),
            count=1,
        )

@pytest.mark.django_db
class TestGeneratePdfPanel:
    @override_settings(DOCRAPTOR_API_KEY="test-api-key")
    def test_get_context_data(self):
        # create a new page
        site = Site.objects.first()
        parent = site.root_page
        page = EditorialPage(title="Test Page", slug="test-page", live=True)
        parent.add_child(instance=page)

        # bind panel to EditorialPage and get for page instance
        panel = GeneratePdfPanel()
        bound_panel = panel.bind_to_model(EditorialPage).get_bound_panel(instance=page)
        context = bound_panel.get_context_data()

        # should use page's URL; api key from settings
        assert context["url"] == page.get_url()
        assert context["DOCRAPTOR_API_KEY"] == "test-api-key"
        assert not context["DOCRAPTOR_LIMIT_NOTE"]

        # make an unpublished change. URL should now be an empty string
        page.title = "test"
        rev = page.save_revision()
        bound_panel = panel.bind_to_model(EditorialPage).get_bound_panel(instance=page)
        context = bound_panel.get_context_data()
        assert context["url"] == ""

        # publish the change. URL should work again
        page.publish(rev)
        page.refresh_from_db()
        bound_panel = panel.bind_to_model(EditorialPage).get_bound_panel(instance=page)
        context = bound_panel.get_context_data()
        assert context["url"] == page.get_url()


class TestEditorialPage(WagtailPageTestCase):
    fixtures = ["wagtail_pages"]

    def setUp(self):
        # login so we have permission to test creating a page
        self.login()

    def test_parent_pages(self):
        self.assertAllowedParentPageTypes(EditorialPage, [EditorialIndexPage])

    def test_subpages(self):
        self.assertAllowedSubpageTypes(EditorialPage, [])

    def test_can_create(self):
        self.assertCanCreateAt(EditorialIndexPage, EditorialPage)
        parent = EditorialIndexPage.objects.first()
        # first test without authors, since they're optional
        self.assertCanCreate(
            parent,
            EditorialPage,
            nested_form_data(
                {
                    "title": "Essay",
                    "slug": "essay",
                    "date": date.today(),
                    "body": streamfield([("paragraph", rich_text("some analysis"))]),
                    "authors": streamfield([]),
                    "editors": streamfield([]),
                }
            ),
        )

        # now check that this can be done with the person snippet,
        # both with and without url
        foo = Person.objects.create(name="foo", url="http://bar.com/")
        bar = Person.objects.create(name="bar")
        self.assertCanCreate(
            parent,
            EditorialPage,
            nested_form_data(
                {
                    "title": "Essay2",
                    "slug": "essay2",
                    "date": date.today(),
                    "body": streamfield([("paragraph", rich_text("some analysis"))]),
                    "authors": streamfield([("author", foo.pk), ("author", bar.pk)]),
                    "editors": streamfield([]),
                }
            ),
        )

    def test_set_url_path(self):
        index_page = EditorialIndexPage.objects.first()
        editorial_page = EditorialPage.objects.first()

        # test existing url path for published page from fixture
        url_path = editorial_page.set_url_path(index_page)
        assert url_path.startswith(index_page.url_path)
        assert url_path.endswith("{}/".format(editorial_page.slug))
        assert editorial_page.first_published_at.strftime("/%Y/%m/") in url_path

        # no parent
        assert editorial_page.set_url_path(None) == "/"

        # no published date (i.e. draft post); should use current date
        editorial_page.first_published_at = None
        url_path = editorial_page.set_url_path(index_page)
        assert date.today().strftime("/%Y/%m/") in url_path

    def test_template_rendering(self):
        # For EditorialIndexPage's equivalent, see test_routing
        editorial_page = EditorialPage.objects.get(
            title__icontains="Test Page with Authors"
        )
        site = Site.objects.first()
        editorial_url = editorial_page.relative_url(site)
        response = self.client.get(editorial_url)
        # basic template/content check
        self.assertContains(response, editorial_page.title)
        # each author should be shown twice: visible and in head metadata
        person_a = Person.objects.get(name="Person A")
        person_b = Person.objects.get(name="Person B")
        self.assertContains(response, person_a.name, count=2)
        self.assertContains(response, person_b.name, count=2)
        # the date of the post's publication should be present with slash
        self.assertContains(
            response,
            editorial_page.first_published_at.strftime("%B %-d, %Y"),
            count=1,
        )
        # the url for person A should be present once
        self.assertContains(response, person_a.url, count=1)
        # check order of authors in the page context
        # should be out of alpha order
        response.context["page"]

        # citation metadata should be set in header
        self.assertContains(
            response,
            '<meta name="citation_title" content="%s" />' % editorial_page.title,
            html=True,
        )
        for author in [person_a, person_b]:
            self.assertContains(
                response,
                '<meta name="citation_author" content="%s" />' % person_a.name,
                html=True,
            )
        self.assertContains(
            response,
            '<meta name="citation_publication_date" content="%s" />'
            % editorial_page.first_published_at.strftime("%Y/%m/%d"),
            html=True,
        )
        self.assertContains(
            response,
            '<meta name="citation_publisher" '
            + 'content="Center for Digital Humanities, Princeton University" />',
            html=True,
        )
        request = RequestFactory().get(editorial_url)
        self.assertContains(
            response,
            '<meta name="citation_public_url" content="%s" />'
            % request.build_absolute_uri(),
            html=True,
        )
        # doi and editor not present when not set
        self.assertNotContains(response, "doi:")
        self.assertNotContains(response, "Edited by")
        # add doi, editor, pdf
        editorial_page.doi = "10.1234/56"
        editorial_page.pdf = "http://example.com/path/to/some.pdf"
        # copy authors to editors  (doesn't seem to wokr)
        # editorial_page.editors = editorial_page.authors
        editorial_page.save()
        response = self.client.get(editorial_url)
        self.assertContains(response, f"doi:{editorial_page.doi}")
        self.assertContains(response, f"doi.org/{editorial_page.doi}")
        self.assertContains(response, editorial_page.pdf)
        # additional metadata
        self.assertContains(
            response,
            '<meta name="citation_doi" content="%s" />' % editorial_page.doi,
            html=True,
        )
        self.assertContains(
            response,
            '<meta name="citation_pdf_url" content="%s" />' % editorial_page.pdf,
            html=True,
        )
        # not setting editors correctly
        # self.assertContains(response, "Edited by")
        # for editor in [person_a, person_b]:
        #     self.assertContains(
        #         response,
        #         '<meta name="citation_editor" content="%s" />' % person_a.name,
        #         html=True,
        #     )

        # delete authors
        editorial_page.authors = None
        editorial_page.save()
        response = self.client.get(editorial_url)
        # author should not be shown once
        self.assertNotContains(response, person_a.name)
        self.assertNotContains(response, person_b.name)
        # the date of the post's publication should be present
        # without slash
        self.assertContains(
            response, editorial_page.first_published_at.strftime("%B %-d, %Y"), count=1
        )


class TestPerson(TestCase):
    def test_str(self):
        p = Person(name="A person")
        assert str(p) == "A person"

class TestWagtailHooks:
    @patch("ppa.editorial.wagtail_hooks.render_bundle")
    def test_editor_js(self, mock_render_bundle):
        # should call render_bundle
        mock_script_tag = "<script src='pdf.js'></script>"
        mock_render_bundle.return_value = mock_script_tag
        inserted_js = editor_js()
        mock_render_bundle.assert_called_once_with({}, "pdf", "js")
        assert str(inserted_js) == mock_script_tag
