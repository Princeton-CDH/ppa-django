from django.conf import settings
from django.core.management.base import BaseCommand
from SolrClient import SolrClient, Collections

from ppa.archive import solr


class Command(BaseCommand):
    '''Add fields to schema for configured Solr instance'''
    help = __doc__

    def handle(self, *args, **kwargs):
        schema = solr.SolrSchema()
        created, updated = schema.update_solr_schema()
        # summarize what was done
        if created:
            self.stdout.write('Added %d field%s' %
                (created, '' if created == 0 else 'sg'))
        if updated:
            self.stdout.write('Updated %d field%s' %
                (updated, '' if updated == 0 else 's'))

        # use solr core admin to trigger reload, so schema
        # changes take effect
        solr.CoreAdmin().reload('foo')
