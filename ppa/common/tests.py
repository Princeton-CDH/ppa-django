from unittest.mock import Mock

from django.contrib.auth.models import User, Group
from django.test import TestCase

from ppa.common.admin import LocalUserAdmin
from ppa.common.views import VaryOnHeadersMixin


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
