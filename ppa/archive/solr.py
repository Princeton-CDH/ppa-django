import logging

from parasolr.django import AliasedSolrQuerySet, SolrQuerySet

logger = logging.getLogger(__name__)


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
        "group_id_s",
        "cluster_id_s",
    ]
    # aliases for any fields we want to rename for search and display
    # (must also be included in return_fields list)
    aliases = {
        "source_t": "source",
        "image_id_s": "image_id",
        "first_page_i": "first_page",
        "work_type_s": "work_type",
        "book_journal_s": "book_journal",
        "group_id_s": "group_id",
        "cluster_id_s": "cluster_id",
    }

    keyword_query = None
    within_cluster_id = None

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
        """Add filters to the work query"""
        # filter out empty values to simplify view logic
        # for checking whether query terms are present
        kwargs = dict(
            (opt, val) for opt, val in kwargs.items() if val not in [None, ""]
        )
        if args or kwargs:
            self._workq = self._workq.filter(*args, **kwargs)

    def work_title_search(self, title_query):
        """search works by title"""
        if not title_query:
            return
        # include the edismax title search query in the filters
        self.work_filter(self._title_search)
        # add the actual query content as a query parameter
        # FIXME: maybe all methods should return a new version for consistency
        self.raw_params.update(title_query=title_query)
        # return self.raw_query_parameters(title_query=title_query)

    def keyword_search(self, query):
        """add keyword search"""
        # *store* that there is a keyword present but don't do anything
        # with it yet
        self.keyword_query = query

    def _clone(self):
        # preserve local fields when cloning
        qs_copy = super()._clone()
        qs_copy.keyword_query = self.keyword_query
        qs_copy.within_cluster_id = self.within_cluster_id
        qs_copy._workq = self._workq
        return qs_copy

    def within_cluster(self, cluster_id):
        """Search within a group of reprints/editions"""
        # filter both pages and works by cluster id
        qs_copy = self.filter(cluster_id_s=cluster_id)
        qs_copy.work_filter(cluster_id_s=cluster_id)
        # store the cluster id since it impacts expand/collapse behavior
        qs_copy.within_cluster_id = cluster_id
        return qs_copy

    def query_opts(self):
        """Extend default query options method to combine work and keyword
        search options based on what filters are present."""

        # create a queryset copy to update
        qs_copy = self.all()

        # for main archive search, by default we collapse on
        # cluster id to collect all reprints/editions and their pages;
        # when searching within a cluster, collapse on group id
        collapse_on = "group_id_s" if self.within_cluster_id else "cluster_id_s"

        # @NOTE: Role of order here in separating works from pages (works < pages) may need to be revisited eventually.
        collapse_filter = '{!collapse field=%s sort="order asc"}' % collapse_on
        
        # We can apply collapse here since we need it for both keyword query case and not
        # Remember that cluster_id_s is now defined as `str(self.cluster) if self.cluster else index_id` in models.py.
        # So collapsing by "cluster" id implicitly includes works with no cluster id set.
        qs_copy = qs_copy.filter(collapse_filter)

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

        content_query = "content:(%s)" % self.keyword_query
        qs_copy = (
            qs_copy.search(combined_query)
            # .filter(collapse_filter)     # This no longer needed since applied above in `qs_copy = qs_copy.filter(collapse_filter)`
            .raw_query_parameters(
                content_query=content_query,
                keyword_query=self.keyword_query,
                # expand="true",
                work_query=work_query,
                # **{"expand.rows": 1},
            )
        )

        return qs_copy._base_query_opts()

    def _base_query_opts(self):
        # provide access to regular query opts logic, bypassing keyword/join
        return super().query_opts()



class PageSearchQuerySet(AliasedSolrQuerySet):
    # aliases for any fields we want to rename for search and display
    # includes non-renamed fields to push them into the return
    field_aliases = {
        "id":"id",
        "score":"score",
        "source": "source_id",
        "image_id": "image_id_s",
        "group_id": "group_id_s",
        "cluster_id": "cluster_id_s",
    }