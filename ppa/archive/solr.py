import logging

from django.conf import settings
import requests
from SolrClient import SolrClient


logger = logging.getLogger(__name__)


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
        {'name': 'srcid', 'type': 'string', 'required': False},
        {'name': 'content', 'type': 'text_en', 'required': False},
        {'name': 'item_type', 'type': 'string', 'required': False},
        {'name': 'title', 'type': 'text_en', 'required': False},
        {'name': 'enumcron', 'type': 'string', 'required': False},
        {'name': 'author', 'type': 'text_en', 'required': False},
        {'name': 'pub_date', 'type': 'string', 'required': False},
        {'name': 'pub_place', 'type': 'text_en', 'required': False},
        {'name': 'publisher', 'type': 'text_en', 'required': False},
        {'name': 'src_url', 'type': 'string', 'required': False},
        {'name': 'order', 'type': 'string', 'required': False},
        {'name': 'collections', 'type': 'text_en', 'required': False,
         'multiValued': True},
        {'name': 'text', 'type': 'text_en', 'required': False, 'stored': False,
         'multiValued': True},

         # sort/facet copy fields
        {'name': 'title_exact', 'type': 'string', 'required': False},
        {'name': 'author_exact', 'type': 'string', 'required': False},
        {'name': 'collections_exact', 'type': 'string', 'required': False,
         'multiValued': True}
    ]
    # fields to be copied into general purpose text field for searching
    text_fields = ['srcid', 'content', 'title', 'author', 'pub_date', 'enumcron',
        'pub_place', 'publisher']
    copy_fields = [
        ('title', 'title_exact'),
        ('author', 'author_exact'),
        ('collections', 'collections_exact'),
    ]
    # todo: facet fields

    def __init__(self):
        self.solr, self.solr_collection = get_solr_connection()
        logger.info('Using %s core.', self.solr_collection)

    def solr_schema_fields(self):
        '''List of currently configured Solr schema fields'''
        schema_info = self.solr.schema.get_schema_fields(self.solr_collection)
        return [field['name'] for field in schema_info['fields']]

    def update_solr_schema(self):
        '''Update the configured solr instance schema to match
        the configured fields.  Returns a tuple with the number of fields
        created and updated.'''
        try:
            current_fields = self.solr_schema_fields()
        except ConnectionRefusedError:
            raise

        created = updated = removed = 0
        for field in self.fields:
            if field['name'] not in current_fields:
                self.solr.schema.create_field(self.solr_collection, field)
                created += 1
            else:
                self.solr.schema.replace_field(self.solr_collection, field)
                updated += 1

        # remove and recreate copy fields to avoid adding them multiple times
        copy_fields = self.solr.schema.get_schema_copyfields(self.solr_collection)

        current_cp_fields = []
        for field in self.text_fields:
            cp_field = {'source': field, 'dest': 'text'}
            current_cp_fields.append(cp_field)
            if cp_field not in copy_fields:
                self.solr.schema.create_copy_field(self.solr_collection,
                    cp_field)
        for src_field, dest_field in self.copy_fields:
            cp_field = {'source': src_field, 'dest': dest_field}
            current_cp_fields.append(cp_field)
            if cp_field not in copy_fields:
                self.solr.schema.create_copy_field(self.solr_collection,
                    cp_field)

        # delete previous copy cp fields that are no longer wanted
        for cp_field in copy_fields:
            if cp_field not in current_cp_fields:
                self.solr.schema.delete_copy_field(self.solr_collection, cp_field)

        # remove previously defined fields that are no longer current
        field_names = [field['name'] for field in self.fields]
        for field in current_fields:
            # don't remove special fields!
            if field == 'id' or field.startswith('_'):
                continue
            if field not in field_names:
                removed += 1
                self.solr.schema.delete_field(self.solr_collection, field)

        return (created, updated, removed)


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


class PagedSolrQuery(object):
    # wrap solrclient query in a way that allows search results to be
    # paginated by django paginator

    query_opts = {}
    _result = None

    def __init__(self, query_opts=None):
        self.solr, self.solr_collection = get_solr_connection()

        self.query_opts = query_opts or {}
        # possibly should default to 'q': '*:*' ...

    def add_facet(self, facet_name):
        '''Add a facet to the paged query and set facet = true'''
        if 'facet' not in self.query_opts:
            self.query_opts['facet'] = 'true'
            self.query_opts['facet.field'] = [facet_name]
        else:
            self.query_opts['facet.field'].append(facet_name)

    def get_facets(self):
        '''Wrap SolrClient.SolrResponse.get_facets() to get query facets as a dict
        of dicts.'''
        if self._result is None:
            self.get_results()
        return self._result.get_facets()

    def get_results(self):
        self._result = self.solr.query(self.solr_collection, self.query_opts)
        return self._result.docs

    def count(self):
        if self._result is None:
            query_opts = self.query_opts.copy()
            query_opts['rows'] = 0
            self._result = self.solr.query(self.solr_collection, query_opts)

        return self._result.get_num_found()

    def get_json(self):
        '''Return query response as JSON data, to allow full access to anything
        included in Solr data.'''
        if self._result is None:
            self.get_results()
        return self._result.get_json()

    def set_limits(self, start, stop):
        '''Return a subsection of the results, to support slicing.'''
        # FIXME: it probably matters here that solr start is 1-based ...
        if start is None:
            start = 0
        self.query_opts.update({
            'start': start,
            'rows': stop - start + 1
        })

    def __getitem__(self, k):
        '''Return a single result or a slice of results'''
        # based on django queryset logic
        if not isinstance(k, (int, slice)):
            raise TypeError
        assert ((not isinstance(k, slice) and (k >= 0)) or
                (isinstance(k, slice) and (k.start is None or k.start >= 0) and
                 (k.stop is None or k.stop >= 0))), \
            "Negative indexing is not supported."

        if isinstance(k, slice):
            # qs = self._chain() # do we need something like this?
            if k.start is not None:
                start = int(k.start)
            else:
                start = None
            if k.stop is not None:
                stop = int(k.stop)
            else:
                stop = None
            self.set_limits(start, stop)
            # qs.query.set_limits(start, stop)
            # return list(qs)[::k.step] if k.step else qs
            return list(self.get_results())[::k.step] if k.step else self.get_results()

        # single item
        # qs = self._chain()
        self.set_limits(k, k + 1)
        # qs.query.set_limits(k, k + 1)
        # qs._fetch_all()
        return self.get_results()[0]
        # return qs._result_cache[0]
