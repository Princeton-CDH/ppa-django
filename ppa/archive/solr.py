import logging

from parasolr import schema


logger = logging.getLogger(__name__)


class SolrTextField(schema.SolrTypedField):
    field_type = 'text_en'


class SolrSchema(schema.SolrSchema):
    '''Solr Schema declaration.'''

    item_type = schema.SolrStringField()
    # source_id cannot be string_i because Textfield cannot be used in
    # collapse query
    source_id = schema.SolrStringField()
    content = SolrTextField()
    title = SolrTextField()
    subtitle = SolrTextField()
    # TODO make sort_title string_i
    sort_title = schema.SolrStringField()
    enumcron = schema.SolrStringField()
    author = SolrTextField()
    pub_date = schema.SolrField('int')
    pub_place = SolrTextField()
    publisher = SolrTextField()
    source_url = schema.SolrStringField()
    order = schema.SolrStringField()
    collections = SolrTextField(multivalued=True)
    notes = SolrTextField()
    # page fields
    label = SolrTextField()
    tags = SolrTextField(multivalued=True)

    # sort/facet copy fields
    author_exact = schema.SolrStringField()
    collections_exact = schema.SolrStringField(multivalued=True)

    # fields without stemming for search boosting
    title_nostem = schema.SolrField('text_nostem', stored=False)
    subtitle_nostem = schema.SolrField('text_nostem', stored=False)
    content_nostem = schema.SolrField('text_nostem', stored=False)

    # have solr automatically track last index time
    last_modified = schema.SolrField('date', default='NOW')

    #: define copy fields for facets and unstemmed variants
    copy_fields = {
        'author': 'author_exact',
        'collections': 'collections_exact',
        'title': 'title_nostem',
        'subtitle': 'subtitle_nostem',
        'content': 'content_nostem',
    }


class OldSolrSchema(object):
    '''Solr Schema object.  Includes project schema configuration and
    methods to update configured Solr instance.'''

    # ported from winthrop-django
    field_types = [
        {
            'name': 'text_en',
            "class": "solr.TextField",
            # for now, configuring index and query analyzers the same
            # if we want synonyms, query must be separate
            "analyzer": {
                # "charFilters": [],
                "tokenizer": {
                    "class": "solr.StandardTokenizerFactory",
                },
                "filters": [
                    {"class": "solr.StopFilterFactory", "ignoreCase": True,
                     "words": "lang/stopwords_en.txt"},
                    {"class": "solr.LowerCaseFilterFactory"},
                    {"class": "solr.EnglishPossessiveFilterFactory"},
                    {"class": "solr.KeywordMarkerFilterFactory"},
                    {"class": "solr.PorterStemFilterFactory"},
                    {"class": "solr.ICUFoldingFilterFactory"},
                ]
            }
        },
        # text with no stemming, so exact matches can be prioritized
        {
            'name': 'text_nostem',
            "class": "solr.TextField",
            # for now, configuring index and query analyzers the same
            # if we want synonyms, query must be separate
            "analyzer": {
                # "charFilters": [],
                "tokenizer": {
                    "class": "solr.StandardTokenizerFactory",
                },
                "filters": [
                    {"class": "solr.StopFilterFactory", "ignoreCase": True,
                     "words": "lang/stopwords_en.txt"},
                    {"class": "solr.LowerCaseFilterFactory"},
                    {"class": "solr.EnglishPossessiveFilterFactory"},
                    {"class": "solr.KeywordMarkerFilterFactory"},
                    {"class": "solr.ICUFoldingFilterFactory"},
                ]
            }
        },
        {
            'name': 'string_i',
            "class": "solr.TextField",
            "sortMissingLast": True,
            "analyzer": {
                "tokenizer": {
                    # treat entire field as a single token
                    "class": "solr.KeywordTokenizerFactory",
                },
                "filters": [
                    # lower case to ensure alphabetical sort behaves as
                    # expected and standardize using
                    # the ICUFoldingFilterFactory
                    # {"class": "solr.LowerCaseFilterFactory"},
                    {"class": "solr.ICUFoldingFilterFactory"},

                ]
            },
        },
        # {
        #     'name': 'text_with_punctuation',
        #     "class":"solr.TextField",
        #     # for now, configuring index and query analyzers the same
        #     # if we want synonyms, query must be separate
        #     "analyzer": {
        #         # "charFilters": [],
        #         "tokenizer": {
        #             "class": "solr.WhitespaceTokenizerFactory",
        #         },
        #         "filters": [
        #             {"class": "solr.LowerCaseFilterFactory"},
        #             {"class": "solr.ICUFoldingFilterFactory"},
        #         ]
        #     }
        # },
    ]

    #: solr schema field definitions
    fields = [
        # source_id cannot be string_i because Textfield cannot be used in
        # collapse query
        {'name': 'source_id', 'type': 'string', 'required': False},
        {'name': 'content', 'type': 'text_en', 'required': False},
        {'name': 'item_type', 'type': 'string', 'required': False},
        {'name': 'title', 'type': 'text_en', 'required': False},
        {'name': 'subtitle', 'type': 'text_en', 'required': False},
        {'name': 'sort_title', 'type': 'string_i', 'required': False},
        {'name': 'enumcron', 'type': 'string', 'required': False},
        {'name': 'author', 'type': 'text_en', 'required': False},
        {'name': 'pub_date', 'type': 'int', 'required': False},
        {'name': 'pub_place', 'type': 'text_en', 'required': False},
        {'name': 'publisher', 'type': 'text_en', 'required': False},
        {'name': 'source_url', 'type': 'string', 'required': False},
        {'name': 'order', 'type': 'string', 'required': False},
        {'name': 'collections', 'type': 'text_en', 'required': False,
         'multiValued': True},
        {'name': 'notes', 'type': 'text_en', 'required': False},
        # page fields
        {'name': 'label', 'type': 'text_en', 'required': False},
        {'name': 'tags', 'type': 'string', 'required': False, 'multiValued': True},

        # sort/facet copy fields
        {'name': 'author_exact', 'type': 'string', 'required': False},
        {'name': 'collections_exact', 'type': 'string', 'required': False,
         'multiValued': True},
        {'name': 'content_nostem', 'type': 'text_nostem', 'required': False, 'stored': False},

        # fields without stemming for search boosting
        {'name': 'title_nostem', 'type': 'text_nostem', 'required': False, 'stored': False},
        {'name': 'subtitle_nostem', 'type': 'text_nostem', 'required': False, 'stored': False},

        # have solr automatically track last modification time for
        # indexed content
        {'name': 'last_modified', 'type': 'date', 'default': 'NOW'},

        # Punctuation search
        # {'name': 'content_punctuation', 'type': 'text_with_punctuation', 'required': False, 'stored': False},
    ]
    #: fields to be copied into general purpose text field for searching
    text_fields = []
    # NOTE: superceded by query field configuration in solr config

    # #: copy fields, e.g. for facets
    copy_fields = [
        ('author', 'author_exact'),
        ('collections', 'collections_exact'),
        ('title', 'title_nostem'),
        ('subtitle', 'subtitle_nostem'),
        ('content', 'content_nostem'),
        # ('content', 'content_punctuation')
    ]

    def __init__(self):
        self.solr, self.solr_collection = get_solr_connection()
        logger.info('Using %s core.', self.solr_collection)

    def solr_schema_fields(self):
        '''List of currently configured Solr schema fields'''
        schema_info = self.solr.schema.get_schema_fields(self.solr_collection)
        return [field['name'] for field in schema_info['fields']]

    def solr_schema_field_types(self):
        '''Dictionary of currently configured Solr schema fields'''
        response = self.solr.schema.get_schema_field_types(self.solr_collection)
        return {field_type['name']: field_type for field_type in response['fieldTypes']}

    def update_solr_schema(self):
        '''Update the configured solr instance schema to match
        the configured fields.  Returns a tuple with the number of fields
        created and updated.'''

        current_field_types = self.solr_schema_field_types()

        for field_type in self.field_types:
            if field_type['name'] in current_field_types:
                # if field exists but definition has changed, replace it
                if field_type != current_field_types[field_type['name']]:
                    self.solr.schema.replace_field_type(self.solr_collection, field_type)
            # otherwise, create as a new field
            else:
                self.solr.schema.create_field_type(self.solr_collection, field_type)

            # TODO: deletion?

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
