from django.conf import settings
import requests
from SolrClient import SolrClient


def get_solr_connection():
    '''Initialize a Solr connection using project settings'''
    # TODO: error handling on config not present?
    solr_config = settings.SOLR_CONNECTIONS['default']
    solr = SolrClient(solr_config['URL'])
    # NOTE: may want to extend SolrClient to set a default collection
    solr_collection = solr_config['COLLECTION']
    return solr, solr_collection


class SolrSchema(object):
    '''Solr Schema object.  Includes project schema configuration and
    methods to update configured Solr instance.'''

    #: solr field definitions for basic fields
    fields = [
        {'name': 'htid', 'type': 'string', 'required': False},
        {'name': 'content', 'type': 'text_en', 'required': False},
        {'name': 'item_type', 'type': 'string', 'required': False},
        {'name': 'title', 'type': 'text_en', 'required': False},
        {'name': 'enumcron', 'type': 'string', 'required': False},
        {'name': 'author', 'type': 'text_en', 'required': False},
        {'name': 'pub_date', 'type': 'string', 'required': False},
        {'name': 'pub_place', 'type': 'string', 'required': False},
        {'name': 'publisher', 'type': 'string', 'required': False},
        {'name': 'text', 'type': 'text_en', 'required': False, 'stored': False,
         'multiValued': True},
    ]
    # fields to be copied into general purpose text field for searching
    text_fields = ['htid', 'content', 'title', 'author', 'pub_date', 'enumcron',
        'pub_place', 'publisher']
    # todo: facet fields

    def __init__(self):
        self.solr, self.solr_collection = get_solr_connection()

    def solr_schema_fields(self):
        '''List of currently configured Solr schema fields'''
        schema_info = self.solr.schema.get_schema_fields(self.solr_collection)
        return [field['name'] for field in schema_info['fields']]

    def update_solr_schema(self):
        '''Update the configured solr instance schema to match
        the configured fields.  Returns a tuple with the number of fields
        created and updated.'''
        current_fields = self.solr_schema_fields()
        created = updated = 0
        for field in self.fields:
            if field['name'] not in current_fields:
                self.solr.schema.create_field(self.solr_collection, field)
                created += 1
            else:
                self.solr.schema.replace_field(self.solr_collection, field)
                updated += 1

        for field in self.text_fields:
            self.solr.schema.create_copy_field(self.solr_collection,
                {'source': field, 'dest': 'text'})

        # NOTE: doesn't remove fields in solr that are
        # no longer configured

        return (created, updated)


class CoreAdmin(object):
    '''Solr Core Admin API wrapper'''

    def __init__(self):
        self.admin_url = settings.SOLR_CONNECTIONS['default'].get('ADMIN_URL', None)

    def reload(self, core=None):
        '''Reload an existing Solr core, e.g. so that schema changes
        take effect.  If core is not specified, uses the configured
        project collection/core.'''
        if core is None:
            core = settings.SOLR_CONNECTIONS['default'].get('COLLECTION')
        response = requests.get(self.admin_url,
            params={'action': 'RELOAD', 'core': core})
        return response.status_code == requests.codes.ok


