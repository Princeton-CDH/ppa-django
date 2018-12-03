from time import sleep

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.template.defaultfilters import striptags
from wagtail.core.models import Page, Site
from wagtail.tests.utils import WagtailPageTests
from wagtail.tests.utils.form_data import nested_form_data, streamfield, \
    rich_text
import pytest

from ppa.archive.models import Collection, DigitizedWork
from ppa.archive.solr import get_solr_connection
from ppa.pages.models import HomePage, ContentPage, CollectionPage
from ppa.editorial.models import EditorialIndexPage


class TestHomePage(WagtailPageTests):
    fixtures = ['wagtail_pages']

    # NOTE: can't check assertCanCreate since it requires
    # a root page

    def setUp(self):
        super().setUp()
        # get homepage instance from fixture
        self.home = HomePage.objects.first()

        # collection page for testing homepage context & template logic
        self.collection_page = CollectionPage.objects.create(
            title='All About My PPA Collections',
            slug='collections',
            depth=self.home.depth + 1,
            show_in_menus=False,
            path=self.home.path + '0003',
            content_type=ContentType.objects.get_for_model(CollectionPage),
            body=rich_text('You want a collection?'),
        )

    def test_can_create(self):
        root = Page.objects.get(title='Root')
        self.assertCanCreateAt(Page, HomePage)
        self.assertCanNotCreateAt(ContentPage, HomePage)
        self.assertCanCreate(root, HomePage, nested_form_data({
            'title': 'PPA',
            'slug': 'newhome',
            'body': rich_text('intro to PPA'),
            # 'page_preview_1': None,
            # 'page_preview_2': None,
        }))

    def test_parent_pages(self):
        self.assertAllowedParentPageTypes(
            HomePage, [Page])

    def test_subpages(self):
        self.assertAllowedSubpageTypes(
            HomePage, [ContentPage, EditorialIndexPage, CollectionPage, Page])

    @pytest.mark.usefixtures("solr")
    def test_get_context(self):
        # Create test collections to display
        coll1 = Collection.objects.create(name='Random Grabbag')
        dictionary = Collection.objects.create(name='Dictionary')
        context = self.home.get_context({})
        assert 'collections' in context
        assert len(context['collections']) == 2
        assert coll1 in context['collections']
        # no longer excluding dictionary collections
        assert dictionary in context['collections']
        assert 'stats' in context
        assert 'collection_page' in context
        assert context['collection_page'] == self.collection_page

        # Add a third collection
        coll2 = Collection.objects.create(
            name='Bar through Time',
            description='A somewhat less useful collection.'
        )
        context = self.home.get_context({})
        # only two collections should be returned in the response
        assert len(context['collections']) == 2

    @pytest.mark.usefixtures("solr")
    def test_template(self):
        # Check that the template is rendering as expected
        site = Site.objects.first()
        coll1 = Collection.objects.create(name='Random Grabbag')
        coll2 = Collection.objects.create(
            name='Foo through Time',
            description="A <em>very</em> useful collection."
        )

        response = self.client.get(self.home.relative_url(site))

        # - basic checks right templates
        self.assertTemplateUsed(response, 'base.html')
        self.assertTemplateUsed(response, 'pages/home_page.html')
        # - detailed checks of template
        self.assertContains(
            response, coll1.name,
            msg_prefix='should list a collection called Random Grabbag'
        )
        self.assertContains(
            response, coll2.name,
            msg_prefix='should list a collection called Foo through Time'
        )
        self.assertContains(
            response, coll2.description, html=True,
            msg_prefix='should render the description with HTML intact.'
        )
        # - collection page display
        self.assertContains(response, self.collection_page.title,
            msg_prefix='should render collection page title')
        self.assertContains(response, self.collection_page.body,
            msg_prefix='should include collection page body content')
        self.assertContains(response, self.collection_page.relative_url(site),
            msg_prefix='should link to collection page')


class TestContentPage(WagtailPageTests):
    fixtures = ['wagtail_pages']

    def test_can_create(self):
        self.assertCanCreateAt(HomePage, ContentPage)
        root = HomePage.objects.first()
        self.assertCanCreate(root, ContentPage, nested_form_data({
            'title': 'About of the PPA',
            'slug': 'about',
            'body': streamfield([
                ('paragraph', rich_text('some analysis'))
            ])
        }))

    def test_parent_pages(self):
        self.assertAllowedParentPageTypes(
            ContentPage, [HomePage, ContentPage, Page])

    def test_subpages(self):
        self.assertAllowedSubpageTypes(
            ContentPage, [ContentPage, Page])

    def test_get_description(self):
        '''test page preview mixin'''
        # fixture with body content and no description
        content_page = ContentPage.objects.first()

        assert not content_page.description
        desc = content_page.get_description()
        # length excluding tags should be truncated to max length or less
        assert len(striptags(desc)) <= content_page.max_length
        # beginning of text should match exactly the *first* block
        # (excluding end of content because truncation is inside tags)
        assert desc[:200] == str(content_page.body[0])[:200]

        # empty tags in description shouldn't be used
        content_page.description = '<p></p>'
        desc = content_page.get_description()
        assert desc[:200] == str(content_page.body[0])[:200]

        # test content page with image for first block
        content_page2 = ContentPage(
            title='What is Prosody?',
            body=[
                ('image', '<img src="milton-example.png"/>'),
                ('paragraph', '<p>Prosody today means both the study of versification and pronunciation</p>'),
                ('paragraph', '<p>More content here...</p>'),
            ]
        )
        # should ignore image block and use first paragraph content
        assert content_page2.get_description()[:200] == \
            str(content_page2.body[1])[:200]

        # should use description field when set
        content_page2.description = '<p>A short intro to prosody.</p>'
        assert content_page2.get_description() == content_page2.description

        # should truncate if description content is too long
        content_page2.description = content_page.body[0]
        assert len(striptags(content_page.get_description())) \
            <= content_page.max_length

    def test_get_plaintext_description(self):
        # description set but no search description
        content_page = ContentPage(
            title='What is Prosody?',
            description='<p>A short intro to prosody.</p>'
        )
        assert content_page.get_plaintext_description() == \
            striptags(content_page.description)

        # use search description when set
        content_page.search_description = 'A different description for meta text.'
        assert content_page.get_plaintext_description() == \
            content_page.search_description


class TestCollectionPage(WagtailPageTests):
    fixtures = ['wagtail_pages', 'sample_digitized_works']

    def setUp(self):
        super().setUp()
        self.home = HomePage.objects.first()
        self.collection_page = CollectionPage.objects.create(
            title='About the Collections',
            slug='collections',
            depth=self.home.depth + 1,
            show_in_menus=False,
            path=self.home.path + '0003',
            content_type=ContentType.objects.get_for_model(CollectionPage)
        )

    def test_can_create(self):
        self.assertCanCreateAt(HomePage, CollectionPage)
        self.assertCanCreate(self.home, CollectionPage, nested_form_data({
            'title': 'About the Collections',
            'slug': 'more-collections',
            'body': rich_text('collection overview here...'),
        }))

    def test_parent_pages(self):
        self.assertAllowedParentPageTypes(
            CollectionPage, [HomePage])

    def test_subpages(self):
        self.assertAllowedSubpageTypes(
            CollectionPage, [])

    @pytest.mark.usefixtures("solr")
    def test_get_context(self):
        # Create test collections to display
        coll1 = Collection.objects.create(name='Random Grabbag')
        dictionary = Collection.objects.create(name='Dictionary')
        coll2 = Collection.objects.create(
            name='Foo through Time',
            description="A <em>very</em> useful collection."
        )

        context = self.collection_page.get_context({})
        assert 'collections' in context
        assert 'stats' in context

        # should include all collections
        assert 'collections' in context
        assert len(context['collections']) == Collection.objects.count()
        assert 'stats' in context

    @pytest.mark.usefixtures("solr")
    def test_template(self):
        # Check that the template is rendering as expected
        site = Site.objects.first()
        coll1 = Collection.objects.create(name='Random Grabbag')
        coll2 = Collection.objects.create(
            name='Foo through Time',
            description="A <em>very</em> useful collection."
        )
        empty_coll = Collection.objects.create(name='Empty Box')

        # add items to collections to check stats & links
        # - put everything in collection 1
        digworks = DigitizedWork.objects.all()
        for digwork in digworks:
            digwork.collections.add(coll1)
        # just one item in collection 2
        wintry = digworks.get(title__icontains='Wintry')
        wintry.collections.add(coll2)

        # reindex the digitized works so we can check stats
        solr, solr_collection = get_solr_connection()
        solr.index(solr_collection, [dw.index_data() for dw in digworks],
                   params={"commitWithin": 100})
        sleep(2)

        response = self.client.get(self.collection_page.relative_url(site))

        # - check that correct templates are used
        self.assertTemplateUsed(response, 'base.html')
        self.assertTemplateUsed(response, 'pages/content_page.html')
        self.assertTemplateUsed(response, 'pages/collection_page.html')
        # - check user-editable page content displayed
        self.assertContains(response, self.collection_page.body)
        # - check collection display
        self.assertContains(
            response, coll1.name,
            msg_prefix='should list a collection called Random Grabbag'
        )
        self.assertContains(
            response, coll2.name,
            msg_prefix='should list a collection called Foo through Time'
        )
        self.assertContains(
            response, coll2.description, html=True,
            msg_prefix='should render the description with HTML intact.'
        )

        # - check collection stats displayed on template
        self.assertContains(response, '%d digitized works' % digworks.count())
        self.assertContains(response, '1 digitized work')
        self.assertNotContains(response, '1 digitized works')
        self.assertContains(response, '1880–1904')
        self.assertContains(response, '1903')
        # - check collection search links
        archive_url = reverse('archive:list')
        self.assertContains(response, 'href="%s?collections=%s"' % (archive_url, coll1.pk))
        self.assertContains(response, 'href="%s?collections=%s"' % (archive_url, coll2.pk))
        # empty collection should not link
        self.assertNotContains(response, 'href="%s?collections=%s"' % (archive_url, empty_coll.pk))
