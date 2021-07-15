import logging

from parasolr import schema
from parasolr.django import AliasedSolrQuerySet, SolrQuerySet

logger = logging.getLogger(__name__)


class SolrTextField(schema.SolrTypedField):
    field_type = "text_en"


class UnicodeTextAnalyzer(schema.SolrAnalyzer):
    """Solr text field analyzer with unicode folding. Includes all standard
    text field analyzers (stopword filters, lower case, possessive,
    porter stemming) and adds ICU folding filter factory.
    Uses a keyword repeat before stemming to preserve original words.
    """

    tokenizer = "solr.StandardTokenizerFactory"
    filters = [
        {
            "class": "solr.StopFilterFactory",
            "ignoreCase": True,
            "words": "lang/stopwords_en.txt",
        },
        {"class": "solr.LowerCaseFilterFactory"},
        {"class": "solr.EnglishPossessiveFilterFactory"},
        {"class": "solr.KeywordRepeatFilterFactory"},
        # customize stemming for decadence
        {
            "class": "solr.StemmerOverrideFilterFactory",
            "dictionary": "stemdict_ppa.txt",
        },
        {"class": "solr.PorterStemFilterFactory"},
        {"class": "solr.ICUFoldingFilterFactory"},
        # remove duplicates after repeat since some stemmed and unstemmed
        # tokens may match
        {"class": "solr.RemoveDuplicatesTokenFilterFactory"},
    ]


class TextKeywordTextAnalyzer(schema.SolrAnalyzer):
    """Text field that acts like a string. Treat the entire field as a
    single token, but apply lower case and unicode folding.
    (Using text because String fields don't have filters.)"""

    tokenizer = "solr.KeywordTokenizerFactory"
    filters = [
        # lower case to ensure alphabetical sort behaves as
        # expected and standardize using ICUFoldingFilterFactory
        {"class": "solr.LowerCaseFilterFactory"},
        {"class": "solr.ICUFoldingFilterFactory"},
    ]


class SolrSchema(schema.SolrSchema):
    """Solr Schema declaration with local field types and fields for PPA."""

    # declare custom field types
    text_en = schema.SolrFieldType("solr.TextField", analyzer=UnicodeTextAnalyzer)
    string_i = schema.SolrFieldType(
        "solr.TextField", analyzer=TextKeywordTextAnalyzer, sortMissingLast=True
    )

    # declare project-specific fields
    item_type = schema.SolrStringField()
    # source_id cannot be string_i because Textfield cannot be used in
    # collapse query
    source_id = schema.SolrStringField()
    content = SolrTextField()
    title = SolrTextField()
    subtitle = SolrTextField()
    sort_title = schema.SolrField("string_i")
    enumcron = schema.SolrStringField()
    author = SolrTextField()
    pub_date = schema.SolrField("int")
    pub_place = SolrTextField()
    publisher = SolrTextField()
    source_url = schema.SolrStringField()
    order = schema.SolrField("int")
    collections = SolrTextField(multivalued=True)
    notes = SolrTextField()
    # page fields
    label = SolrTextField()
    tags = SolrTextField(multivalued=True)

    # sort/facet copy fields
    author_exact = schema.SolrStringField()
    collections_exact = schema.SolrStringField(multivalued=True)

    # have solr automatically track last index time
    last_modified = schema.SolrField("date", default="NOW")

    #: define copy fields for facet/sort
    copy_fields = {
        "author": "author_exact",
        "collections": "collections_exact",
    }


class ArchiveSearchQuerySet(AliasedSolrQuerySet):

    # search title query field syntax
    # (query field configured in solr config; searches title & subtitle with
    # boosting)
    _title_search = (
        "{!type=edismax qf=$search_title_qf " + "pf=$search_title_pf v=$title_query}"
    )
    _keyword_search = "{!type=edismax qf=$keyword_qf pf=$keyword_pf v=$keyword_query}"

    # minimal set of fields to be returned from Solr for search page
    return_fields = [
        "id",
        "author",
        "pubdate",
        "publisher",
        "enumcron",
        "order",
        "source_id",
        "label",
        "title",
        "subtitle",
        "score",
        "pub_date",
        "collections",
        "source_t",
        "image_id_s",
        "first_page_i",
        "source_url",
        "work_type_s",
        "book_journal_s",
    ]
    # aliases for any fields we want to rename for search and display
    # (must also be included in return_fields list)
    aliases = {
        "source_t": "source",
        "image_id_s": "image_id",
        "first_page_i": "first_page",
        "work_type_s": "work_type",
        "book_journal_s": "book_journal",
    }

    keyword_query = None

    def __init__(self, solr=None):
        # field aliases: keys return the fields that will be returned from Solr for search page;
        # values provide an aliased name if it should be different than solr index field.
        # use alias if one is set, otherwise use field name
        self.field_aliases = {
            self.aliases.get(key, key): key for key in self.return_fields
        }
        self._workq = SolrQuerySet()
        super().__init__(solr=solr)

    def work_filter(self, *args, **kwargs):
        # filter out empty values to simplify view logic
        # for checking whether query terms are present
        kwargs = dict(
            (opt, val) for opt, val in kwargs.items() if val not in [None, ""]
        )
        if args or kwargs:
            self._workq = self._workq.filter(*args, **kwargs)

    def work_title_search(self, title_query):
        if not title_query:
            return
        # include the edismax title search query in the filters
        self.work_filter(self._title_search)
        # add the actual query content as a query parameter
        # FIXME: maybe all methods should return a new version for consistency
        self.raw_params.update(title_query=title_query)
        # return self.raw_query_parameters(title_query=title_query)

    def keyword_search(self, query):
        # *store* that there is a keyword present but don't do anything
        # with it yet
        self.keyword_query = query

    def _clone(self):
        # preserve local fields when cloning
        qs_copy = super()._clone()
        qs_copy.keyword_query = self.keyword_query
        qs_copy._workq = self._workq
        return qs_copy

    def query_opts(self):
        """Extend default query options method to combine work and keyword
        search options based on what filters are present."""

        # create a queryset copy to update
        qs_copy = self.all()

        # if there is no keyword search present, only works should
        # be returned; add item type filter and use filters from work queryset
        if not self.keyword_query:
            self.work_filter(item_type="work")
            qs_copy.filter_qs.extend(self._workq.filter_qs)
            # use set to ensure we don't duplicate a filter
            qs_copy.filter_qs = list(set(qs_copy.filter_qs))
            return qs_copy._base_query_opts()

        # when there is a keyword query, add it & combine with any work filters
        # combine all work filter queries into a single query

        # search across keyword qf fields OR find works with pages that match
        keyword_query = (
            "((%s) OR ({!join from=group_id_s to=id v=$content_query}))"
            % self._keyword_search
        )
        # by default, set combined query to keyword query (= no work filters)
        combined_query = keyword_query

        # if there are work filters, combine them with keyword
        work_query = ""
        if self._workq.filter_qs:
            # convert filter queries to a single ANDed search query
            work_query = "(%s)" % " AND ".join(self._workq.filter_qs)
            # find works based on filter query but also restrict pages to those
            # that match works with these filters
            combined_query = (
                "(%s) AND (%s OR {!join from=id to=group_id_s v=$work_query})"
                % (keyword_query, work_query)
            )
            # pass combined workfilter query as a raw query parameter
            qs_copy = qs_copy.raw_query_parameters(work_query=work_query)

        # search on the combined work/page join query
        # use collapse to group pages with work by source id
        # expand and return three rows
        # NOTE: expand param used to be 2, but that wasn't generating
        # correct display! Not sure why
        qs_copy = (
            qs_copy.search(combined_query)
            .filter('{!collapse field=group_id_s sort="order asc"}')
            .raw_query_parameters(
                content_query="content:(%s)" % self.keyword_query,
                keyword_query=self.keyword_query,
                expand="true",
                work_query=work_query,
                **{"expand.rows": 2},
            )
        )

        return qs_copy._base_query_opts()

    def _base_query_opts(self):
        # provide access to regular query opts logic, bypassing keyword/join
        return super().query_opts()
