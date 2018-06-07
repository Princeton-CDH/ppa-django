from unittest.mock import Mock, patch
from weakref import ref

from django.conf import settings
from django.db import models
from django.test import TestCase, override_settings
import pytest

from ppa.archive.models import Collection, DigitizedWork
from ppa.archive.signals import IndexableSignalHandler


def setUpModule():
    print('module setup')
    # rebind indexing signal handlers for this test module only
    IndexableSignalHandler.setup()

def tearDownModule():
    print('module teardown')
    # disconnect indexing signal handlers
    IndexableSignalHandler.teardown()


@override_settings(SOLR_CONNECTIONS={'default': settings.SOLR_CONNECTIONS['test']})
class TestIndexableSignalHandler(TestCase):

    def test_setup(self):
        # check that signal handlers are bound as expected
        # - model save and delete
        post_save_handlers = [item[1] for item in models.signals.post_save.receivers]
        assert ref(IndexableSignalHandler.handle_save) in post_save_handlers
        post_del_handlers = [item[1] for item in models.signals.post_delete.receivers]
        assert ref(IndexableSignalHandler.handle_delete) in post_del_handlers
        # many to many
        m2m_handlers = [item[1] for item in models.signals.m2m_changed.receivers]
        assert ref(IndexableSignalHandler.handle_relation_change) in m2m_handlers

        # testing related handlers based on DigitizedWork config
        pre_save_handlers = [item[1] for item in models.signals.pre_save.receivers]
        assert ref(DigitizedWork.handle_collection_save) in pre_save_handlers
        pre_del_handlers = [item[1] for item in models.signals.pre_delete.receivers]
        assert ref(DigitizedWork.handle_collection_delete) in pre_del_handlers

    @pytest.mark.django_db
    def test_handle_save(self):
        with patch.object(DigitizedWork, 'index') as mockindex:
            DigitizedWork.objects.create(source_id='njp.32101013082597')
            mockindex.assert_called_with(params=IndexableSignalHandler.index_params)

        # non-indexable object should be ignored
        nonindexable = Mock()
        IndexableSignalHandler.handle_save(Mock(), nonindexable)
        nonindexable.index.assert_not_called()

    @pytest.mark.django_db
    def test_handle_delete(self):
        with patch.object(DigitizedWork, 'index'):
            with patch.object(DigitizedWork, 'remove_from_index') as mock_rmindex:
                digwork = DigitizedWork.objects.create(source_id='njp.32101013082597')
                digwork.delete()
                mock_rmindex.assert_called_with(params=IndexableSignalHandler.index_params)

        # non-indexable object should be ignored
        nonindexable = Mock()
        IndexableSignalHandler.handle_delete(Mock(), nonindexable)
        nonindexable.remove_from_index.assert_not_called()

    @pytest.mark.django_db
    def test_handle_relation_change(self):
        with patch.object(DigitizedWork, 'index') as mockindex:
            digwork = DigitizedWork.objects.create(source_id='njp.32101013082597')
            coll1 = Collection.objects.create(name='all the things')
            coll2 = Collection.objects.create(name='some of the things')

            # add to collection
            mockindex.reset_mock()
            digwork.collections.add(coll1)
            digwork.collections.add(coll2)
            mockindex.assert_called_with(params=IndexableSignalHandler.index_params)

            # remove from collection
            mockindex.reset_mock()
            digwork.collections.remove(coll2)
            mockindex.assert_called_with(params=IndexableSignalHandler.index_params)

            # clear
            mockindex.reset_mock()
            digwork.collections.clear()
            mockindex.assert_called_with(params=IndexableSignalHandler.index_params)

            # if action is not one we care about, should be ignored
            mockindex.reset_mock()
            IndexableSignalHandler.handle_relation_change(Mock(), digwork, 'pre_remove')
            mockindex.assert_not_called()

        # non-indexable object should be ignored
        nonindexable = Mock()
        IndexableSignalHandler.handle_relation_change(Mock(), nonindexable, 'post_add')
        nonindexable.index.assert_not_called()
