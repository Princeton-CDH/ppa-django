from unittest.mock import patch, Mock

from django import forms
from django.contrib.admin.sites import AdminSite
from django.http import HttpResponseRedirect
from django.test import TestCase, override_settings, RequestFactory
from django.urls import reverse

from ppa.archive.admin import DigitizedWorkAdmin
from ppa.archive.models import DigitizedWork

TEST_SOLR_CONNECTIONS = {
    'default': {
        'COLLECTION': 'testppa',
        'URL': 'http://localhost:191918984/solr/',
        'ADMIN_URL': 'http://localhost:191918984/solr/admin/cores'
    }
}


class TestDigitizedWorkAdmin(TestCase):

    fixtures = ['sample_digitized_works']

    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(SOLR_CONNECTIONS=TEST_SOLR_CONNECTIONS)
    @patch('ppa.archive.solr.get_solr_connection')
    @patch('ppa.archive.models.DigitizedWork.index')
    def test_save_related(self, mockindex, mock_get_solr_connection):
        '''Test that override of save_related calls index'''
        # fake request
        request = self.factory.get('/madeup/url')
        # fake adminsite
        site = AdminSite()
        # make a digital work to get in overridden method
        digwork = DigitizedWork.objects.create(source_id='njp.32101013082597')
        # mocked form
        form = Mock()
        form.instance.pk = digwork.pk
        form.save_m2m = Mock()
        digadmin = DigitizedWorkAdmin(DigitizedWork, site)
        # call save_related using mocks for most params we don't use or need
        digadmin.save_related(request, form, [], False)
        # mocked index method of the digwork object should have been called
        digwork.index.assert_called_with(params={'commitWithin': 10000})

    def test_bulk_add_collection(self):
        # create a DigitizedWorkAdmin object
        digworkadmin = DigitizedWorkAdmin(DigitizedWork, AdminSite())
        fakerequest = Mock()
        fakerequest.session = {}
        queryset = DigitizedWork.objects.all()
        redirect = digworkadmin.bulk_add_collection(fakerequest, queryset)
        # should return a redirect
        assert isinstance(redirect, HttpResponseRedirect)
        # url should reverse the appropriate route
        assert redirect.url == reverse('archive:add-to-collection')
        # session on request should be set with a key called collection-add-ids
        # that is not empty
        assert fakerequest.session['collection-add-ids']
        # the key should have the ids of the three fixtures
        assert fakerequest.session['collection-add-ids'] == [1, 2, 3]
        redirect = digworkadmin.bulk_add_collection(fakerequest, queryset)
        # test against an empty queryset just in case
        DigitizedWork.objects.all().delete()
        queryset = DigitizedWork.objects.all()
        redirect = digworkadmin.bulk_add_collection(fakerequest, queryset)
        # session variable should be set to an empty list
        assert fakerequest.session['collection-add-ids'] == []
