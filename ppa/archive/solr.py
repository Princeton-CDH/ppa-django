import logging

from parasolr import schema


logger = logging.getLogger(__name__)


class SolrTextField(schema.SolrTypedField):
    field_type = 'text_en'


class UnicodeTextAnalyzer(schema.SolrAnalyzer):
        '''Solr text field analyzer with unicode folding. Includes all standard
        text field analyzers (stopword filters, lower case, possessive, keyword
        marker, porter stemming) and adds ICU folding filter factory.
        '''
        tokenizer = 'solr.StandardTokenizerFactory'
        filters = [
            {"class": "solr.StopFilterFactory", "ignoreCase": True,
             "words": "lang/stopwords_en.txt"},
            {"class": "solr.LowerCaseFilterFactory"},
            {"class": "solr.EnglishPossessiveFilterFactory"},
            {"class": "solr.KeywordMarkerFilterFactory"},
            {"class": "solr.PorterStemFilterFactory"},
            {"class": "solr.ICUFoldingFilterFactory"},
        ]


class UnstemmedTextAnalyzer(schema.SolrAnalyzer):
    '''Solr text field analyzer without unstemming. Exactly the same as
    :class:`UnicodeTextAnalyzer` except without PorterStemFilterFactory.
    Used as a secondary search field, so exact matches can be prioritized
    over stemmed matches.'''
    tokenizer = 'solr.StandardTokenizerFactory'
    filters = [
        {"class": "solr.StopFilterFactory", "ignoreCase": True,
         "words": "lang/stopwords_en.txt"},
        {"class": "solr.LowerCaseFilterFactory"},
        {"class": "solr.EnglishPossessiveFilterFactory"},
        {"class": "solr.KeywordMarkerFilterFactory"},
        {"class": "solr.ICUFoldingFilterFactory"},
    ]


class TextKeywordTextAnalyzer(schema.SolrAnalyzer):
    '''Text field that acts like a string. Treat the entire field as a
    single token, but apply lower case and unicode folding.
    (Using text because String fields don't have filters.)'''

    tokenizer = 'solr.KeywordTokenizerFactory'
    filters = [
        # lower case to ensure alphabetical sort behaves as
        # expected and standardize using ICUFoldingFilterFactory
        {"class": "solr.LowerCaseFilterFactory"},
        {"class": "solr.ICUFoldingFilterFactory"},
    ]
    # TODO where do we specify this?
    # "sortMissingLast": True,


class SolrSchema(schema.SolrSchema):
    '''Solr Schema declaration.'''

    # declare custom field types
    text_en = schema.SolrFieldType(
        'solr.TextField', analyzer=UnicodeTextAnalyzer)
    text_nostem = schema.SolrFieldType(
        'solr.TextField', analyzer=UnstemmedTextAnalyzer)
    string_i = schema.SolrFieldType(
        'solr.TextField', analyzer=TextKeywordTextAnalyzer,
        sortMissingLast=True)

    # declare project-specific fields
    item_type = schema.SolrStringField()
    # source_id cannot be string_i because Textfield cannot be used in
    # collapse query
    source_id = schema.SolrStringField()
    content = SolrTextField()
    title = SolrTextField()
    subtitle = SolrTextField()
    sort_title = schema.SolrField('string_i')
    enumcron = schema.SolrStringField()
    author = SolrTextField()
    pub_date = schema.SolrField('int')
    pub_place = SolrTextField()
    publisher = SolrTextField()
    source_url = schema.SolrStringField()
    order = schema.SolrField('int')
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
