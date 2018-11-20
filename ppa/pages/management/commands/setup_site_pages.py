'''
**setup_site_pages** is a custom manage command to install
a default set of pages and menus for the Wagtail CMS. It is designed not to
touch other content.

Example usage::

    python manage.py setup_site_pages
'''
from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from wagtail.core.models import Site as WagtailSite, Page

from ppa.pages.models import HomePage, ContentPage, CollectionPage
from ppa.editorial.models import EditorialIndexPage


class Command(BaseCommand):
    '''Setup initial wagtail site and pages needed for PPA navigation'''
    help = __doc__

    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    content_pages = {
        'history': 'History of the Archive',
        'prosody': 'What is Prosody',
        'search': 'How to Search',
        'cite': 'How to Cite',
        'contributors': 'Contributors and Board Members',
        'contact': 'Contact Us',
    }

    def handle(self, *args, **kwargs):
        # wagtail creates the root page for us
        root = Page.objects.get(slug='root')

        # NOTE: logic for creating pages based on wagtail core migration
        # 0002 initial data, which creates initial site and welcome page

        # delete default home wagtail home page
        Page.objects.filter(slug='home', title__contains='Welcome').delete()

        # Create PPA homepage
        home = HomePage.objects.filter(slug='home').first()
        if not home:
            home = HomePage.objects.create(
                title='Princeton Prosody Archive',
                slug='home',
                depth=2,
                numchild=0,
                show_in_menus=True,
                path='00010001',
                content_type=ContentType.objects.get_for_model(HomePage),
            )

        home.show_in_menus = True
        home.path = '00010001'
        home.url_path = '/home/'
        home.save()

        # create editorial index page
        editorial = EditorialIndexPage.objects.first()
        if not editorial:
            editorial = EditorialIndexPage.objects.create(
                title='Editorial',
                slug='editorial',
                depth=home.depth + 1,
                show_in_menus=False,
                path=home.path + '0001',
                content_type=ContentType.objects.get_for_model(EditorialIndexPage)
            )

        ## create collections page
        collections = CollectionPage.objects.first()
        if not collections:
            collections = CollectionPage.objects.create(
                title='About the Collections',
                slug='collections',
                depth=home.depth + 1,
                show_in_menus=False,
                path=home.path + '0002',
                content_type=ContentType.objects.get_for_model(CollectionPage)
            )

        # create content page stubs if they are not already present
        index = 3
        for slug, title in self.content_pages.items():
            cpage = ContentPage.objects.filter(slug=slug).first()
            if not cpage:
                ContentPage.objects.create(
                    title=title,
                    slug=slug,
                    depth=home.depth + 1,
                    path='{}{:04d}'.format(home.path, index),
                    show_in_menus=True,
                    content_type=ContentType.objects.get_for_model(ContentPage)
                )
            index += 1

        # create wagtail site from django site and associate new homepage
        # self.create_wagtail_site(home)
        self.create_wagtail_site(home.page_ptr)

        # associate default page previews for home page if not set
        if not any([home.page_preview_1, home.page_preview_2]):
            home.page_preview_1 = ContentPage.objects.get(slug='prosody')
            home.page_preview_2 = ContentPage.objects.get(slug='history')
            home.save()

        # let treebeard fix the hierarchy
        Page.fix_tree()

    def create_wagtail_site(self, root_page):
        '''Create a wagtail site object from the current default
        Django site.'''
        current_site = Site.objects.get(pk=settings.SITE_ID)

        # split domain into name and port
        if ':' in current_site.domain:
            domain, port = current_site.domain.split(':')
        else:
            domain = current_site.domain
            port = 80

        # create wagtail site with same config and associate home page
        wagtail_site, created = WagtailSite.objects.get_or_create(hostname=domain, port=port,
            site_name=current_site.name, root_page=root_page,
            is_default_site=True)

        return wagtail_site
