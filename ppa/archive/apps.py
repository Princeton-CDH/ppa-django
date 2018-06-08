from django.apps import AppConfig


class ArchiveConfig(AppConfig):
    name = 'ppa.archive'

    def ready(self):
        # import and connect signal handlers for Solr indexing
        from ppa.archive.signals import IndexableSignalHandler

