from django.contrib.auth.models import User, Group
from django.test import TestCase
from django.urls import reverse
from wagtail.core.templatetags.wagtailcore_tags import slugurl

from ppa.common.admin import LocalUserAdmin


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
        response = self.client.get('/sitemap-pages.xml')
        for slug in ['home', 'history', 'editorial']:
            self.assertContains(response, slugurl({}, slug))
