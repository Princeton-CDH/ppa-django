from unittest.mock import patch, Mock

from django.contrib.admin.sites import AdminSite
from django.http import HttpResponseRedirect
from django.test import TestCase, override_settings, RequestFactory
from django.urls import reverse

from ppa.archive.admin import DigitizedWorkAdmin
from ppa.archive.models import DigitizedWork, Collection, ProtectedWorkFieldFlags


class TestDigitizedWorkAdmin(TestCase):

    fixtures = ['sample_digitized_works']

    def setUp(self):
        self.factory = RequestFactory()

    def test_list_collections(self):
        # set up preliminary objects needed to test an admin site object
        site = AdminSite()
        digadmin = DigitizedWorkAdmin(DigitizedWork, site)

        # no collections should return an empty string
        digwork = DigitizedWork.objects.create(source_id='njp.32101013082597')
        coll_list = digadmin.list_collections(digwork)
        assert coll_list == ''

        # create two collections and set them on digwork
        Z = Collection.objects.create(name='Z Collection')
        A = Collection.objects.create(name='A Collection')
        C = Collection.objects.create(name='C Collection')

        digwork.collections.set([Z, A, C])

        # should now return an alphabetized, comma separated list
        coll_list = digadmin.list_collections(digwork)
        assert coll_list == 'A Collection, C Collection, Z Collection'

    def test_source_link(self):
        # set up preliminary objects needed to test an admin site object
        site = AdminSite()
        digadmin = DigitizedWorkAdmin(DigitizedWork, site)
        # create digitalwork with a source_id and source_url
        # test and method assume that we can always count on these
        fake_url='http://obviouslywrongurl.org/njp.32101013082597'
        digwork = DigitizedWork.objects.create(
            source_id='njp.32101013082597',
            source_url=fake_url
        )
        snippet = digadmin.source_link(digwork)
        assert snippet == \
            '<a href="%s" target="_blank">njp.32101013082597</a>' % fake_url

    def test_readonly_fields(self):
        site = AdminSite()
        digadmin = DigitizedWorkAdmin(DigitizedWork, site)

        assert digadmin.get_readonly_fields(Mock()) == digadmin.readonly_fields

        # hathi record
        hathi_work = DigitizedWork.objects.first()
        assert set(digadmin.get_readonly_fields(Mock(), hathi_work)) == \
            set(digadmin.readonly_fields + digadmin.hathi_readonly_fields)


    def test_save_model(self):
        request = self.factory.get('/madeup/url')
        site = AdminSite()
        digwork = DigitizedWork(source_id='njp.32101013082597')
        form = Mock()
        change = False
        digadmin = DigitizedWorkAdmin(DigitizedWork, site)
        # initially created, so work should just be saved, no flags set
        digadmin.save_model(request, digwork, form, change)
        saved_work = DigitizedWork.objects.get(source_id=digwork.source_id)
        assert saved_work == digwork
        assert saved_work.protected_fields == ProtectedWorkFieldFlags.no_flags
        saved_work.title = 'Test Title'
        saved_work.enumcron = '0001'
        change = True
        # saved work should now set the flags for the altered fields
        digadmin.save_model(request, saved_work, form, change)
        new_work = DigitizedWork.objects.get(pk=saved_work.pk)
        assert new_work.protected_fields == \
            ProtectedWorkFieldFlags.title | ProtectedWorkFieldFlags.enumcron

    @patch('ppa.archive.models.DigitizedWork.index')
    def test_save_related(self, mockindex):
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
        digwork.index.assert_called_with()

    def test_add_works_to_collection(self):
        # create a DigitizedWorkAdmin object
        digworkadmin = DigitizedWorkAdmin(DigitizedWork, AdminSite())
        fakerequest = Mock()
        fakerequest.session = {}
        # set some arbitary querystring filters
        fakerequest.GET = {'q': 1, 'foo': 'bar'}
        queryset = DigitizedWork.objects.all()
        redirect = digworkadmin.add_works_to_collection(fakerequest, queryset)
        # should return a redirect
        assert isinstance(redirect, HttpResponseRedirect)
        # url should reverse the appropriate route
        assert redirect.url == reverse('archive:add-to-collection')
        # session on request should be set with a key called collection-add-ids
        # that is not empty
        assert fakerequest.session['collection-add-ids']
        # the key should have the ids of the three fixtures
        assert set(fakerequest.session['collection-add-ids']) == \
            set(queryset.values_list('id', flat=True))
        # the querystring should have been faithfully copied to session as well
        assert fakerequest.session['collection-add-filters'] == fakerequest.GET
        redirect = digworkadmin.add_works_to_collection(fakerequest, queryset)
        # test against an empty queryset just in case
        DigitizedWork.objects.all().delete()
        queryset = DigitizedWork.objects.all()
        redirect = digworkadmin.add_works_to_collection(fakerequest, queryset)
        # session variable should be set to an empty list
        assert fakerequest.session['collection-add-ids'] == []

    @patch('ppa.archive.admin.SolrClient')
    def test_suppress_works(self, mock_solrclient):
        # initialize DigitizedWorkAdmin
        digworkadmin = DigitizedWorkAdmin(DigitizedWork, AdminSite())
        with patch.object(digworkadmin, 'message_user') as mock_message_user:
            fakerequest = Mock()
            # test on all fixture objects
            queryset = DigitizedWork.objects.all()
            all_ids = list(DigitizedWork.objects.values_list('source_id', flat=True))
            print(all_ids)
            digworkadmin.suppress_works(fakerequest, queryset)

            # all items should now be suppressed
            assert DigitizedWork.objects.filter(status=DigitizedWork.SUPPRESSED).count()\
                == len(all_ids)
            # items should be cleared from solr by source id
            mock_solrclient.return_value.update.delete_by_query.assert_called_with(
                'source_id:(%s)' % ' OR '.join(['"%s"' % sid for sid in all_ids])
            )
            mock_message_user.assert_called_with(
                fakerequest, 'Suppressed %d digitized works.' % len(all_ids))

            # call again with objects already suppressed
            mock_solrclient.reset_mock()
            digworkadmin.suppress_works(fakerequest, DigitizedWork.objects.all())
            # shouldn't even initialize solr
            assert mock_solrclient.call_count == 0
            mock_message_user.assert_called_with(
                fakerequest,
                'Suppressed 0 digitized works. Skipped %d (already suppressed).'
                % len(all_ids))
