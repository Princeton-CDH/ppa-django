from django.apps import AppConfig


class ArchiveConfig(AppConfig):
    name = 'ppa.archive'

    def ready(self):
        # import and bind signal handler for Solr indexing
        from ppa.archive.signals import IndexableSignalHandler

