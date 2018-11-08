from wagtail.core.models import Page, Site
from wagtail.tests.utils import WagtailPageTests
from wagtail.tests.utils.form_data import nested_form_data, streamfield
import pytest

from ppa.archive.models import Collection
from ppa.archive.tests.conftest import solr
from ppa.pages.models import HomePage, ContentPage
from ppa.editorial.models import EditorialIndexPage


class TestHomePage(WagtailPageTests):
    fixtures = ['wagtail_pages']

    # NOTE: can't check assertCanCreate since it requires
    # a root page

    def setUp(self):
         # create homepage instance for testing
        self.home = HomePage.objects.first()
        # create(
            # title='PPA', slug='home', depth=0, path='/home/',
            # live=True)

    def test_parent_pages(self):
        self.assertAllowedParentPageTypes(
            HomePage, [])

    def test_subpages(self):
        self.assertAllowedSubpageTypes(
            HomePage, [ContentPage, EditorialIndexPage, Page])

    @pytest.mark.usefixtures("solr")
    def test_get_context(self):
        # Create test collections to display
        coll1 = Collection.objects.create(name='Random Grabbag')
        dictionary = Collection.objects.create(name='Dictionary')
        context = self.home.get_context({})
        assert 'collections' in context
        # non-public collections should be excluded
        assert dictionary not in context['collections']

        coll2 = Collection.objects.create(
            name='Foo through Time',
            description="A <em>very</em> useful collection."
        )

        context = self.home.get_context({})
        # it should have both collections that exist in it
        assert 'collections' in context
        assert len(context['collections']) == 2
        assert coll1 in context['collections']
        assert coll2 in context['collections']
        assert 'stats' in context

        # Add another collection
        coll3 = Collection.objects.create(
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



