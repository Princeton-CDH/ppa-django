import logging

from django.db import models

from ppa.archive.solr import Indexable

logger = logging.getLogger(__name__)


class IndexableSignalHandler:

    index_within = 3

    index_params = {'commitWithin': index_within * 1000}

    def handle_save(sender, instance, **kwargs):
        print('handle save, args %s', kwargs)
        if isinstance(instance, Indexable):
            logger.debug('Indexing %r', instance)
            instance.index(params=IndexableSignalHandler.index_params)

    def handle_delete(sender, instance, **kwargs):
        logger.debug('Deleting %r from index', instance)
        instance.remove_from_index(params=IndexableSignalHandler.index_params)

    def handle_relation_change(sender, instance, action, **kwargs):
        # print('handle relation change %s -> %s - %s %s' % (sender, instance, action, kwargs))
        # handle both add and remove;  do we need to handle clear?
        if action in ['post_add', 'post_remove']:
            if isinstance(instance, Indexable):
                logger.debug('Indexing %r', instance)
                instance.index(params=IndexableSignalHandler.index_params)

    def setup():  # rename to bind?

        # bind to save and delete signals for indexable subclasses
        for model in Indexable.__subclasses__():
            logger.debug('Registering signal handlers for %s', model)
            models.signals.post_save.connect(IndexableSignalHandler.handle_save, sender=model)
            models.signals.post_delete.connect(IndexableSignalHandler.handle_delete, sender=model)

        Indexable.identify_index_dependencies()
        for m2m_rel in Indexable.m2m:
            logger.debug('Registering m2m signal handler for %s', m2m_rel)
            models.signals.m2m_changed.connect(IndexableSignalHandler.handle_relation_change,
                                               sender=m2m_rel)

        for model, options in Indexable.related.items():
            if 'save' in options:
                logger.debug('Registering save signal handler for %s', model)
                models.signals.post_save.connect(options['save'], sender=model)
            if 'delete' in options:
                logger.debug('Registering delete signal handler for %s', model)
                models.signals.pre_delete.connect(options['delete'], sender=model)

    def teardown():  # rename to disconnect?
        # disconnect signal handlers
        for model in Indexable.__subclasses__():
            models.signals.post_save.disconnect(IndexableSignalHandler.handle_save, sender=model)
            models.signals.post_delete.disconnect(IndexableSignalHandler.handle_delete, sender=model)

        # TODO: should also disconnect m2m and related model signal handlers


IndexableSignalHandler.setup()
