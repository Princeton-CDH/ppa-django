from time import sleep
from unittest.mock import Mock

import bleach
from django.template.defaultfilters import striptags
from django.test import SimpleTestCase, RequestFactory
from django.urls import reverse
from wagtail.models import Page, Site
from wagtail.images.models import Image
from wagtail.rich_text import RichText
from wagtail.test.utils import WagtailPageTestCase
from wagtail.test.utils.form_data import nested_form_data, rich_text, streamfield

from ppa.archive.models import Collection, DigitizedWork
from ppa.editorial.models import EditorialIndexPage
from ppa.pages.models import (
    CollectionPage,
    ContentPage,
    ContributorPage,
    HomePage,
    ImageWithCaption,
    LinkableSectionBlock,
    Person,
    SVGImageBlock,
)


class TestHomePage(WagtailPageTestCase):
    fixtures = ["wagtail_pages"]

    # NOTE: can't check assertCanCreate since it requires
    # a root page

    def setUp(self):
        super().setUp()
        # get homepage instance from fixture
        self.home = HomePage.objects.first()

        # collection page for testing homepage context & template logic
        self.collection_page = CollectionPage(
            title="All About My PPA Collections",
            slug="collections",
            # depth=self.home.depth + 1,
            show_in_menus=False,
            # path=self.home.path + "0003",
            # content_type=ContentType.objects.get_for_model(CollectionPage),
            body=rich_text("You want a collection?"),
        )
        # add child sets depth and path
        self.home.add_child(instance=self.collection_page)

        # login so we can test creating pages
        self.login()

    def test_can_create(self):
        root = Page.objects.get(title="Root")
        self.assertCanCreateAt(Page, HomePage)
        self.assertCanNotCreateAt(ContentPage, HomePage)
        self.assertCanCreate(
            root,
            HomePage,
            nested_form_data(
                {
                    "title": "PPA",
                    "slug": "newhome",
                    "body": rich_text("intro to PPA"),
                    # 'page_preview_1': None,
                    # 'page_preview_2': None,
                }
            ),
        )

    def test_parent_pages(self):
        self.assertAllowedParentPageTypes(HomePage, [Page])

    def test_subpages(self):
        self.assertAllowedSubpageTypes(
            HomePage,
            [ContentPage, EditorialIndexPage, CollectionPage, ContributorPage, Page],
        )

    def test_get_context(self):
        # Create test collections to display
        coll1 = Collection.objects.create(name="Random Grabbag")
        dictionary = Collection.objects.create(name="Dictionary")
        context = self.home.get_context({})
        assert "collections" in context
        assert len(context["collections"]) == 2
        assert coll1 in context["collections"]
        # no longer excluding dictionary collections
        assert dictionary in context["collections"]
        assert "stats" in context
        assert "collection_page" in context
        assert context["collection_page"] == self.collection_page

        # Add a third collection
        Collection.objects.create(
            name="Bar through Time", description="A somewhat less useful collection."
        )
        context = self.home.get_context({})
        # only two collections should be returned in the response
        assert len(context["collections"]) == 2

    def test_template(self):
        # Check that the template is rendering as expected
        site = Site.objects.first()
        coll1 = Collection.objects.create(name="Random Grabbag")
        coll2 = Collection.objects.create(
            name="Foo through Time", description="A <em>very</em> useful collection."
        )

        response = self.client.get(self.home.relative_url(site))

        # - basic checks right templates
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "pages/home_page.html")
        # - detailed checks of template
        self.assertContains(
            response,
            coll1.name,
            msg_prefix="should list a collection called Random Grabbag",
        )
        self.assertContains(
            response,
            coll2.name,
            msg_prefix="should list a collection called Foo through Time",
        )
        self.assertContains(
            response,
            coll2.description,
            html=True,
            msg_prefix="should render the description with HTML intact.",
        )
        # - collection page display
        self.assertContains(
            response,
            self.collection_page.title,
            msg_prefix="should render collection page title",
        )
        self.assertContains(
            response,
            self.collection_page.body,
            msg_prefix="should include collection page body content",
        )
        self.assertContains(
            response,
            self.collection_page.relative_url(site),
            msg_prefix="should link to collection page",
        )


class TestContentPage(WagtailPageTestCase):
    fixtures = ["wagtail_pages"]

    def setUp(self):
        # login so we can test creating page
        self.login()

    def test_can_create(self):
        self.assertCanCreateAt(HomePage, ContentPage)
        root = HomePage.objects.first()
        self.assertCanCreate(
            root,
            ContentPage,
            nested_form_data(
                {
                    "title": "About of the PPA",
                    "slug": "about",
                    "body": streamfield([("paragraph", rich_text("some analysis"))]),
                }
            ),
        )

    def test_parent_pages(self):
        self.assertAllowedParentPageTypes(ContentPage, [HomePage, ContentPage, Page])

    def test_subpages(self):
        self.assertAllowedSubpageTypes(ContentPage, [ContentPage, Page])

    def test_get_description(self):
        """test page preview mixin"""
        # fixture with body content and no description
        content_page = ContentPage.objects.first()

        assert not content_page.description
        desc = content_page.get_description()
        # length excluding tags should be truncated to max length or less
        assert len(striptags(desc)) <= content_page.max_length
        # beginning of text should match exactly the *first* block
        # (excluding end of content because truncation is inside tags)

        # should also be cleaned by bleach to its limited set of tags
        assert (
            desc[:200]
            == bleach.clean(
                str(content_page.body[0]),
                # omit 'a' from list of allowed tags
                tags=list(
                    (set(bleach.sanitizer.ALLOWED_TAGS) | set(["p"])) - set(["a"])
                ),
                strip=True,
            )[:200]
        )
        # empty tags in description shouldn't be used
        content_page.description = "<p></p>"
        desc = content_page.get_description()

        # test content page with image for first block
        content_page2 = ContentPage(
            title="What is Prosody?",
            body=[
                ("captioned_image", {"image": '<img src="milton-example.png"/>'}),
                (
                    "paragraph",
                    RichText("<p>Prosody today means both the study of "
                    'and <a href="#">pronunciation</a></p>'),
                ),
                ("paragraph", RichText("<p>More content here...</p>")),
            ],
        )
        # should ignore image block and use first paragraph content
        assert (
            content_page2.get_description()[:200]
            == bleach.clean(
                str(content_page2.body[1]),
                # omit 'a' from list of allowed tags
                tags=list(
                    (set(bleach.sanitizer.ALLOWED_TAGS) | set(["p"])) - set(["a"])
                ),
                strip=True,
            )[:200]
        )

        # should remove <a> tags
        assert '<a href="#">' not in content_page2.get_description()

        # should use description field when set
        content_page2.description = "<p>A short intro to prosody.</p>"
        assert content_page2.get_description() == content_page2.description

        # should truncate if description content is too long
        content_page2.description = content_page.body[0]
        assert len(striptags(content_page.get_description())) <= content_page.max_length

    def test_get_plaintext_description(self):
        # description set but no search description
        content_page = ContentPage(
            title="What is Prosody?", description="<p>A short intro to prosody.</p>"
        )
        assert content_page.get_plaintext_description() == striptags(
            content_page.description
        )

        # use search description when set
        content_page.search_description = "A different description for meta text."
        assert (
            content_page.get_plaintext_description() == content_page.search_description
        )

    def test_template(self):
        # test fixture display
        site = Site.objects.first()
        content_page = ContentPage.objects.first()
        response = self.client.get(content_page.relative_url(site))
        self.assertTemplateUsed(response, "pages/content_page.html")
        self.assertContains(
            response,
            'class="footnotes"',
            msg_prefix="footnotes block should get footnotes class",
        )


class TestCollectionPage(WagtailPageTestCase):
    fixtures = ["wagtail_pages", "sample_digitized_works"]

    def setUp(self):
        super().setUp()
        self.home = HomePage.objects.first()
        self.collection_page = CollectionPage(
            title="About the Collections",
            slug="collections",
            # depth=self.home.depth + 1,
            show_in_menus=False,
            # path=self.home.path + "0003",
            # content_type=ContentType.objects.get_for_model(CollectionPage),
        )
        self.home.add_child(instance=self.collection_page)
        # login so we can test page creation
        self.login()

    def test_can_create(self):
        self.assertCanCreateAt(HomePage, CollectionPage)
        self.assertCanCreate(
            self.home,
            CollectionPage,
            nested_form_data(
                {
                    "title": "About the Collections",
                    "slug": "more-collections",
                    "body": rich_text("collection overview here..."),
                }
            ),
        )

    def test_parent_pages(self):
        self.assertAllowedParentPageTypes(CollectionPage, [HomePage])

    def test_subpages(self):
        self.assertAllowedSubpageTypes(CollectionPage, [])

    def test_get_context(self):
        # Create test collections to display
        Collection.objects.create(name="Random Grabbag")
        Collection.objects.create(name="Dictionary")
        Collection.objects.create(
            name="Foo through Time", description="A <em>very</em> useful collection."
        )

        context = self.collection_page.get_context({})
        assert "collections" in context
        assert "stats" in context

        # should include all collections
        assert "collections" in context
        assert len(context["collections"]) == Collection.objects.count()
        assert "stats" in context

    def test_template(self):
        # Check that the template is rendering as expected
        site = Site.objects.first()
        coll1 = Collection.objects.create(name="Random Grabbag")
        coll2 = Collection.objects.create(
            name="Foo through Time", description="A <em>very</em> useful collection."
        )
        empty_coll = Collection.objects.create(name="Empty Box")

        # add items to collections to check stats & links
        # - put everything in collection 1
        digworks = DigitizedWork.objects.all()
        for digwork in digworks:
            digwork.collections.add(coll1)
        # just one item in collection 2
        wintry = digworks.get(title__icontains="Wintry")
        wintry.collections.add(coll2)

        # reindex the digitized works so we can check stats
        DigitizedWork.index_items(digworks)
        sleep(2)

        response = self.client.get(self.collection_page.relative_url(site))

        # - check that correct templates are used
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "pages/content_page.html")
        self.assertTemplateUsed(response, "pages/collection_page.html")
        # - check user-editable page content displayed
        self.assertContains(response, self.collection_page.body)
        # - check collection display
        self.assertContains(
            response,
            coll1.name,
            msg_prefix="should list a collection called Random Grabbag",
        )
        self.assertContains(
            response,
            coll2.name,
            msg_prefix="should list a collection called Foo through Time",
        )
        self.assertContains(
            response,
            coll2.description,
            html=True,
            msg_prefix="should render the description with HTML intact.",
        )

        # - check collection stats displayed on template
        self.assertContains(response, "%d digitized works" % digworks.count())
        self.assertContains(response, "1 digitized work")
        self.assertNotContains(response, "1 digitized works")
        self.assertContains(response, "1880–1904")
        self.assertContains(response, "1903")
        # - check collection search links
        archive_url = reverse("archive:list")
        self.assertContains(
            response, 'href="%s?collections=%s"' % (archive_url, coll1.pk)
        )
        self.assertContains(
            response, 'href="%s?collections=%s"' % (archive_url, coll2.pk)
        )
        # empty collection should not link
        self.assertNotContains(
            response, 'href="%s?collections=%s"' % (archive_url, empty_coll.pk)
        )


class TestContributorPage(WagtailPageTestCase):
    fixtures = ["wagtail_pages"]

    def setUp(self):
        # login so we can test page creation
        self.login()

    def test_can_create(self):
        self.assertCanCreateAt(HomePage, ContributorPage)
        root = HomePage.objects.first()
        self.assertCanNotCreateAt(ContentPage, ContributorPage)
        self.assertCanCreate(
            root,
            ContributorPage,
            nested_form_data(
                {
                    "title": "Board Members and Contributors",
                    "slug": "contributors",
                    "contributors": streamfield([]),
                    "board": streamfield([]),
                    "body": streamfield([("paragraph", rich_text("some analysis"))]),
                }
            ),
        )

    def test_parent_pages(self):
        self.assertAllowedParentPageTypes(ContributorPage, [HomePage])

    def test_subpages(self):
        self.assertAllowedSubpageTypes(ContributorPage, [])

    def test_template(self):
        home = Page.objects.filter(url_path="/home/").first()
        site = Site.objects.filter(is_default_site=True).first()
        contrib = ContributorPage(
            title="Contributors and Board Members",
            slug="contributors",
            show_in_menus=False,
        )
        # add child sets depth and path
        home.add_child(instance=contrib)

        Page.objects.get(id=contrib.id)

        # add people as project & board members
        person_a = Person.objects.get(name="Person A")
        person_b = Person.objects.get(name="Person B")
        contrib.contributors.append(("person", person_a, "p1"))
        contrib.board.append(("person", person_b, "p2"))
        contrib.save_revision().publish()

        request = RequestFactory().get(contrib.relative_url(site))
        response = contrib.serve(request)
        # - check that expected template was used
        assert response.template_name == "pages/contributor_page.html"

        # render template response content
        response.render()
        # check contributor name, description, link, project
        self.assertContains(response, person_a.name)
        self.assertContains(response, person_a.url)
        self.assertContains(response, person_a.description)
        self.assertContains(response, person_a.project_role)

        # board memeber name, description
        self.assertContains(response, person_b.name)
        self.assertContains(response, person_b.description)


class TestImageWithCaption(SimpleTestCase):
    def test_render(self):
        block = ImageWithCaption()
        test_img = Mock(spec=Image, url="kitty.png", width=100, height=200)
        # django templates call callables, which Mocks are; return the mock again
        test_img.return_value = test_img
        # for simplicity, use the image for all renditions of the image
        test_img.get_rendition.return_value = test_img
        alt_text = "picture of a kitten"
        # NOTE: using "img" here instead of "image" means we're
        # not actually testing the image logic; but not clear how
        # to mock or use an image object in a test
        html = block.render(
            {"image": test_img, "alternative_text": alt_text, "style": "full"}
        )
        assert '<figure class="full">' in html
        assert '<img srcset="' in html
        assert 'alt="picture of a kitten" ' in html
        # no caption
        assert "<figcaption>" not in html

        # with caption
        caption = "A kitten curled up in the sunshine"
        html = block.render(
            block.to_python(
                {"img": test_img, "alternative_text": alt_text, "caption": caption}
            )
        )
        assert (
            '<figcaption><div class="rich-text">%s</div></figcaption' % caption
        ) in html


class TestSVGImageBlock(SimpleTestCase):
    def test_render(self):
        block = SVGImageBlock()
        test_svg = {"url": "graph.svg"}  # Mock(spec=Document, url='graph.svg')
        alt_text = "membership timeline"
        html = block.render({"image": test_svg, "alternative_text": alt_text})
        assert "<figure " in html
        assert '<img role="img"' in html
        # no caption, no extended description
        assert "<figcaption>" not in html
        assert '<div class="sr-only" ' not in html

        # with caption & extended description
        caption = "membership activity from 1919 to 1942"
        desc = "chart shows activity in 1920 and 1940"
        html = block.render(
            {
                "image": test_svg,
                "alternative_text": alt_text,
                "caption": caption,
                "extended_description": desc,
            }
        )
        assert ("<figcaption>%s</figcaption" % caption) in html
        assert '<div class="sr-only" id="graphsvg-desc">' in html
        assert desc in html


class TestLinkableSectionBlock(SimpleTestCase):
    def test_clean(self):
        block = LinkableSectionBlock()
        cleaned_values = block.clean({"anchor_text": "lending library plans"})
        assert cleaned_values["anchor_text"] == "lending-library-plans"

    def test_render(self):
        block = LinkableSectionBlock()
        html = block.render(
            block.to_python(
                {
                    "title": "Joining the Lending Library",
                    "body": "Info about lending library subscription plans",
                    "anchor_text": "joining-the-lending-library",
                }
            )
        )
        expected_html = """
            <div id="joining-the-lending-library">
            <h2>Joining the Lending Library
            <a class="headerlink" href="#joining-the-lending-library"
               title="Permalink to this section">¶</a>
            </h2>
            <div class="rich-text">
                Info about lending library subscription plans
            </div>
            </div>
        """

        self.assertHTMLEqual(html, expected_html)
