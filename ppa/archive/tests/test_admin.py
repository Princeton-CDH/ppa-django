from unittest.mock import patch, Mock

from django import forms
from django.contrib.admin.sites import AdminSite
from django.test import TestCase, override_settings, RequestFactory

from ppa.archive.admin import DigitizedWorkAdmin
from ppa.archive.models import DigitizedWork

TEST_SOLR_CONNECTIONS = {
    'default': {
        'COLLECTION': 'testppa',
        'URL': 'http://localhost:191918984/solr/',
        'ADMIN_URL': 'http://localhost:191918984/solr/admin/cores'
    }
}


@override_settings(SOLR_CONNECTIONS=TEST_SOLR_CONNECTIONS)
@patch('ppa.archive.solr.get_solr_connection')
class TestDigitizedWorkAdmin(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    @patch('ppa.archive.models.DigitizedWork.index')
    def test_save_related(self, mockindex, mock_get_solr_connection):
        '''Test that override of save_related calls index'''
        # fake form for save_related
        class DigitizedWorkModelForm(forms.ModelForm):
            class Meta:
                model = DigitizedWork
                exclude = []

        # fake request
        request = self.factory.get('/madeup/url')
        # fake adminsite
        site = AdminSite()
        # make a digital work to get in overridden method
        digwork = DigitizedWork.objects.create(source_id='njp.32101013082597')
        form = DigitizedWorkModelForm()
        form.instance.pk = digwork.pk
        form.save_m2m = Mock()
        digadmin = DigitizedWorkAdmin(DigitizedWork, site)
        # call save_related using mocks for most params we don't use or need
        digadmin.save_related(request, form, [], False)
        # mocked index method of the digwork object should have been called
        digwork.index.assert_called_with(params={'commitWithin': 10000})
