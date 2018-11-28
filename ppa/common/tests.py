from unittest.mock import Mock

from django.contrib.auth.models import User, Group
from django.test import RequestFactory, TestCase
from django.urls import reverse
from wagtail.core.models import Site, Page
from wagtail.core.templatetags.wagtailcore_tags import slugurl

from ppa.common.admin import LocalUserAdmin
from ppa.common.views import VaryOnHeadersMixin
from ppa.archive.views import DigitizedWorkListView


class TestLocalUserAdmin(TestCase):

    def test_group_names(self):
        testuser = User.objects.create(username="test")
        local_useradm = LocalUserAdmin(User, '')

        assert local_useradm.group_names(testuser) is None

        grp1 = Group.objects.create(name='testers')
        grp2 = Group.objects.create(name='staff')
        grp3 = Group.objects.create(name='superusers')

        testuser.groups.add(grp1, grp2)
        group_names = local_useradm.group_names(testuser)
        assert grp1.name in group_names
        assert grp2.name in group_names
        assert grp3.name not in group_names



class TestSitemaps(TestCase):
    # basic sanity checks that sitemaps are configured correctly
    fixtures = ['wagtail_pages']

    def test_sitemap_index(self):
        response = self.client.get(reverse('sitemap-index'))
        # template response object, can't check content-type
        for subsitemap in ['pages', 'archive', 'digitizedworks']:
            self.assertContains(response, 'sitemap-{}'.format(subsitemap))

    def test_sitemap_pages(self):
        site = Site.objects.first()
        response = self.client.get('/sitemap-pages.xml')
        for slug in ['history', 'editorial', 'home']:
            # somehow slug=home is returning more than one?
            page = Page.objects.filter(slug=slug).first()
            self.assertContains(
                response, '{}</loc>'.format(page.relative_url(site)))


class TestVaryOnHeadersMixin(TestCase):

    def test_vary_on_headers_mixing(self):

        # stub a View that will always return 405 since no methods are defined
        vary_on_view = \
            VaryOnHeadersMixin(vary_headers=['X-Foobar', 'X-Bazbar'])
        # mock a request because we don't need its functionality
        request = Mock()
        response = vary_on_view.dispatch(request)
        # check for the set header with the values supplied
        assert response['Vary'] == 'X-Foobar, X-Bazbar'



class TestRobotsTxt(TestCase):

    def test_robots_txt(self):
        res = self.client.get('/robots.txt')
        # successfully gets robots.txt
        assert res.status_code == 200
        # is text/plain
        assert res['Content-Type'] == 'text/plain'
        # uses robots.txt template
        assert 'robots.txt' in [template.name for template in res.templates]

        # links to sitemap
        self.assertContains(res, '/sitemap.xml')

        with self.settings(SHOW_TEST_WARNING=False):
            res = self.client.get('/robots.txt')
            self.assertContains(res, 'Disallow: /admin')
            self.assertNotContains(res, 'Twitterbot')
        with self.settings(SHOW_TEST_WARNING=True):
            res = self.client.get('/robots.txt')
            self.assertNotContains(res, 'Disallow: /admin')
            self.assertContains(res, 'Disallow: /')
            self.assertContains(res, 'Twitterbot')


class TestAnalytics(TestCase):

    def test_analytics(self):

        # No analytics setting should default to false
        # use a url that without running setup for Wagtail will use base.html
        url = reverse('archive:list')

        res = self.client.get(url)
        # should not have the script tag to load gtag.js
        self.assertNotContains(
            res,
            'https://www.googletagmanager.com/gtag/js?id=UA-87887700-5'
        )
        # should not have the call to init_gtags.js snippet
        self.assertNotContains(res, 'init_gtags.js')
        with self.settings(INCLUDE_ANALYTICS=True):
            # setting should toggle analytics
            res = self.client.get(url)
            # should have the script tag to load gtag.js
            self.assertContains(
                res,
                'https://www.googletagmanager.com/gtag/js?id=UA-87887700-5'
            )
            # should have the call to init_gtags.js snippet
            self.assertContains(res, 'init_gtags.js')

        # Now test that request.is_preview disables analytics
        request = RequestFactory().get('/')
        request.is_preview = True
        res = DigitizedWorkListView.as_view()(request)
        # should not have analytics snippet
        # should not have the script tag to load gtag.js
        self.assertNotContains(
            res,
            'https://www.googletagmanager.com/gtag/js?id=UA-87887700-5'
        )
        # should not have the call to init_gtags.js snippet
        self.assertNotContains(res, 'init_gtags.js')
