from django.conf import settings
from django.core.management.base import BaseCommand
from SolrClient import SolrClient, Collections


class Command(BaseCommand):
    '''Add fields to schema for configured Solr instance'''
    help = __doc__

    # def add_arguments(self, parser):
    #     parser.add_argument('path', nargs='+',
    #         help='''One or more IIIF Collections or Manifests as file or URL.
    #         Use 'PUL' to import PUL Derrida materials.''')
    #     parser.add_argument('--update', action='store_true',
    #         help='Update previously imported manifests')


    # TODO: figure out where should fields be configured/managed
    fields = [
        {'name': 'htid', 'type': 'string', 'required': False},
        {'name': 'content', 'type': 'text_en', 'required': False},   # TODO text!
        {'name': 'item_type', 'type': 'string', 'required': False},
        {'name': 'title', 'type': 'text_en', 'required': False},
        {'name': 'author', 'type': 'text_en', 'required': False},
        {'name': 'pub_date', 'type': 'string', 'required': False},
        {'name': 'text', 'type': 'text_en', 'required': False, 'stored': False},
        # TODO: copyfield text for searching across everything (fulltext + metadata)
    ]
    text_fields = ['htid', 'content', 'title', 'author', 'pub_date']


    def handle(self, *args, **kwargs):
        # TODO: error handling etc
        solr_config = settings.SOLR_CONNECTIONS['default']

        self.solr = SolrClient(solr_config['URL'])
        self.solr_collection = solr_config['COLLECTION']
        print(self.solr.schema.get_schema_fields(self.solr_collection))

        current_fields = self.schema_fields()
        for field in self.fields:
            # TODO: optional update?
            if field['name'] not in current_fields:
                self.solr.schema.create_field(self.solr_collection, field)
            else:
                self.solr.schema.replace_field(self.solr_collection, field)

        for field in self.text_fields:
            self.solr.schema.create_copy_field(self.solr_collection,
                {'source': field, 'dest': 'text'})

        new_fields = self.schema_fields()
        # TODO: report on added/updated?
        print(new_fields)

        # TODO: use core admin to trigger reload?

    def schema_fields(self):
        schema_info = self.solr.schema.get_schema_fields(self.solr_collection)
        return [field['name'] for field in schema_info['fields']]
