import logging

from django.db import models

from ppa.archive.models import DigitizedWork, Collection
from ppa.archive.solr import Indexable

logger = logging.getLogger(__name__)


class IndexableSignalHandler:

    index_within = 3

    index_params = {'commitWithin': index_within * 1000}

    def handle_save(sender, instance, **kwargs):
        print('handle save, args %s', kwargs)
        logger.debug('Indexing %r', instance)
        if isinstance(instance, Indexable):
            instance.index(params=IndexableSignalHandler.index_params)

    def handle_delete(sender, instance, **kwargs):
        logger.debug('Deleting %r from index', instance)
        instance.remove_from_index(params=IndexableSignalHandler.index_params)

    def handle_relation_change(sender, instance, **kwargs):
        print('handle relation change %s - %s' % (instance, kwargs))
        # handle either post or pre add AND remove

    def setup():
        # bind to save and delete signals for indexable subclasses

        for model in Indexable.__subclasses__():
            logger.debug('Registering signal handlers for %s', model)
            models.signals.post_save.connect(IndexableSignalHandler.handle_save, sender=model)
            models.signals.post_delete.connect(IndexableSignalHandler.handle_delete, sender=model)

        # FIXME: how to infer this?
        models.signals.m2m_changed.connect(IndexableSignalHandler.handle_relation_change, sender=DigitizedWork.collections.through)

    def teardown():
        # disconnect signal handlers
        for model in Indexable.__subclasses__():
            models.signals.post_save.disconnect(IndexableSignalHandler.handle_save, sender=model)
            models.signals.post_delete.disconnect(IndexableSignalHandler.handle_delete, sender=model)


IndexableSignalHandler.setup()
