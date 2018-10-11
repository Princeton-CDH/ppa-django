import itertools
import json
import logging

from cached_property import cached_property
from django.conf import settings
from django.db.models.fields.related_descriptors import ManyToManyDescriptor
from django.db.models.query import QuerySet
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

    #: solr schema field definitions
    fields = [
        {'name': 'srcid', 'type': 'string', 'required': False},
        {'name': 'content', 'type': 'text_en', 'required': False},
        {'name': 'item_type', 'type': 'string', 'required': False},
        {'name': 'title', 'type': 'text_en', 'required': False},
        {'name': 'enumcron', 'type': 'string', 'required': False},
        {'name': 'author', 'type': 'text_en', 'required': False},
        {'name': 'pub_date', 'type': 'int', 'required': False},
        {'name': 'pub_place', 'type': 'text_en', 'required': False},
        {'name': 'publisher', 'type': 'text_en', 'required': False},
        {'name': 'src_url', 'type': 'string', 'required': False},
        {'name': 'order', 'type': 'string', 'required': False},
        {'name': 'collections', 'type': 'text_en', 'required': False,
         'multiValued': True},
        {'name': 'text', 'type': 'text_en', 'required': False, 'stored': False,
         'multiValued': True},
        # page fields
        {'name': 'label', 'type': 'text_en', 'required': False},
        {'name': 'tags', 'type': 'string', 'required': False, 'multiValued': True},

        # sort/facet copy fields
        {'name': 'title_exact', 'type': 'string', 'required': False},
        {'name': 'author_exact', 'type': 'string', 'required': False},
        {'name': 'collections_exact', 'type': 'string', 'required': False,
         'multiValued': True}
    ]
    #: fields to be copied into general purpose text field for searching
    text_fields = ['srcid', 'content', 'title', 'author', 'pub_date', 'enumcron',
                   'pub_place', 'publisher']
    #: copy fields, e.g. for facets
    copy_fields = [
        ('title', 'title_exact'),
        ('author', 'author_exact'),
        ('collections', 'collections_exact'),
    ]

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
        current_fields = self.solr_schema_fields()

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
    '''A Solr query object that wraps a :mod:`SolrClient` query in a way
    that allows search results to be paginated by django paginator.'''

    query_opts = {}
    _result = None

    def __init__(self, query_opts=None):
        self.solr, self.solr_collection = get_solr_connection()

        self.query_opts = query_opts or {}
        # possibly should default to 'q': '*:*' ...

    @property
    def result(self):
        if self._result is None:
            self.get_results()
        return self._result

    def get_facets(self):
        '''Wrap SolrClient.SolrResponse.get_facets() to get query facets as a dict
        of dicts.'''
        return self.result.get_facets()

    def get_facets_ranges(self):
        '''Wrap SolrClient.SolrResponse.get_facets() to get query facets as a dict
        of dicts.'''
        return self.result.get_facets_ranges()

    def get_results(self):
        '''
        Return results of the Solr query.

        :return: docs as a list of dictionaries.
        '''
        self._result = self.solr.query(self.solr_collection, self.query_opts)
        return self._result.docs

    def count(self):
        '''Total number of results in the query'''
        if self._result is None:
            query_opts = self.query_opts.copy()
            query_opts['rows'] = 0
            # FIXME: do we actually want to store the result with no rows?
            self._result = self.solr.query(self.solr_collection, query_opts)

        return self._result.get_num_found()

    def get_json(self):
        '''Return query response as JSON data, to allow full access to anything
        included in Solr data.'''
        return self.result.get_json()

    @cached_property
    def raw_response(self):
        '''Return the raw Solr result to provide access to return sections
        not exposed by SolrClient'''
        return json.loads(self.get_json())

    def get_expanded(self):
        '''get the expanded results from a collapsed query'''
        return self.raw_response.get('expanded', {})

    def get_highlighting(self):
        '''get highlighting results from the response'''
        return self.raw_response.get('highlighting', {})

    def set_limits(self, start, stop):
        '''Return a subsection of the results, to support slicing.'''
        if start is None:
            start = 0
        self.query_opts.update({
            'start': start,
            'rows': stop - start
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


class Indexable(object):
    '''Mixin for objects that are indexed in Solr.  Subclasses must implement
    `index_id` and `index` methods.

    Subclasses may include an `index_depends_on` property which is used
    by :meth:`identify_index_dependencies` to determine index dependencies
    on related objects, including many-to-many relationships.  This property
    should be structured like this::

        index_depends_on = {
            'attr_name': {      # string name of the attribute on this model
                'save': handle_attr_save,  # signal handler for post_save on this model
                'delete': handle_attr_delete,   # signal handler for pre_delete on this model
            }
        }

    If the attribute is a many-to-many field, indexing will be configured on
    the model when the based on relationship changes (a signal handler will
    listen for :class:`models.signals.m2m_changed` on the through model).
    Signal handler methods for save and delete are optional.

    '''

    # TODO: set default solr params / commit within here? maybe get value
    # from django settings?

    #: number of items to index at once when indexing a large number of items
    index_chunk_size = 150

    def index_data(self):
        '''should return a dictionary of data for indexing in Solr'''
        raise NotImplementedError

    def index_id(self):
        '''the value that is used as the Solr id for this object'''
        raise NotImplementedError

    def index(self, params=None):
        '''Index the current object in Solr.  Allows passing in
        parameter, e.g. to set a `commitWithin` value.
        '''
        solr, solr_collection = get_solr_connection()
        solr.index(solr_collection, [self.index_data()], params=params)

    @classmethod
    def index_items(cls, items, params=None, progbar=None):
        '''Indexable class method to index multiple items at once.  Takes a
        list, queryset, or generator of Indexable items or dictionaries.
        Items are indexed in chunks, based on :attr:`Indexable.index_chunk_size`.
        Takes an optional progressbar object to update when indexing items
        in chunks. Returns a count of the number of items indexed.'''
        solr, solr_collection = get_solr_connection()

        # if this is a queryset, use iterator to get it in chunks
        if isinstance(items, QuerySet):
            items = items.iterator()

        # if this is a normal list, convert it to an iterator
        # so we don't iterate the same slice over and over
        elif isinstance(items, list):
            items = iter(items)

        # index in chunks to support efficiently indexing large numbers
        # of items (adapted from index script)
        chunk = list(itertools.islice(items, cls.index_chunk_size))
        count = 0
        while chunk:
            # call index data method if present; otherwise assume item is dict
            solr.index(solr_collection,
                       [i.index_data() if hasattr(i, 'index_data') else i
                        for i in chunk],
                       params=params)
            count += len(chunk)
            # update progress bar if one was passed in
            if progbar:
                progbar.update(count)

            # get the next chunk
            chunk = list(itertools.islice(items, cls.index_chunk_size))

        return count

    def remove_from_index(self, params=None):
        '''Remove the current object from Solr by identifier using
        :meth:`index_id`'''
        solr, solr_collection = get_solr_connection()
        # NOTE: using quotes on id to handle ids that include colons or other
        # characters that have meaning in Solr/lucene queries
        solr.delete_doc_by_id(solr_collection, '"%s"' % self.index_id(), params=params)

    related = None
    m2m = None

    @classmethod
    def identify_index_dependencies(cls):
        # determine and document index dependencies
        # for indexable models based on index_depends_on field

        if cls.related is not None and cls.m2m is not None:
            return

        related = {}
        m2m = []
        for model in Indexable.__subclasses__():
            for dep, opts in model.index_depends_on.items():
                # if a string, assume attribute of model
                if isinstance(dep, str):
                    attr = getattr(model, dep)
                    if isinstance(attr, ManyToManyDescriptor):
                        # store related model and options with signal handlers
                        related[attr.rel.model] = opts
                        # add through model to many to many list
                        m2m.append(attr.through)

        cls.related = related
        cls.m2m = m2m

