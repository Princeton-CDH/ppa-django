import logging
import os
from pathlib import Path

from django.conf import settings

try:
    from parasolr.django import AliasedSolrQuerySet, SolrQuerySet
except Exception:
    from ppa.solr_factory import AliasedSolrQuerySet, SolrQuerySet

logger = logging.getLogger(__name__)

# Maps ISO 639-1 codes to Solr field suffix
_LANG_FIELD_SUFFIX = {
    "ar": "ar", "bg": "bg", "ca": "ca", "cz": "cz",
    "da": "da", "de": "de", "el": "el", "en": "en", "es": "es",
    "et": "et", "eu": "eu", "fa": "fa", "fi": "fi", "fr": "fr",
    "ga": "ga", "gl": "gl", "hi": "hi", "hu": "hu", "hy": "hy",
    "id": "id", "it": "it", "ja": "ja", "ko": "ko", "lv": "lv",
    "nl": "nl", "no": "no", "pt": "pt", "ro": "ro", "ru": "ru",
    "sv": "sv", "th": "th", "tr": "tr",
    "zh": "cjk",
}

_LOW_BOOST_LANGS = {"ja", "ko", "ar", "zh"}


def _build_language_qf():
    """Build a keyword_qf string covering all adapter supported_languages.

    Returns None if no adapters declare supported_languages.
    """
    from ppa.adapters.loader import get_adapter

    supported = set()
    adapters_dir = getattr(settings, "ADAPTERS_DIR", None)
    if adapters_dir and os.path.exists(adapters_dir):
        for item in Path(adapters_dir).iterdir():
            if item.is_dir() and (item / "adapter.yaml").exists():
                adapter = get_adapter(item.name)
                if adapter and adapter.supported_languages:
                    supported.update(adapter.supported_languages)

    if not supported:
        return None

    lang_fields = []
    for lang in sorted(supported):
        suffix = _LANG_FIELD_SUFFIX.get(lang, lang)
        boost = "^10" if lang in _LOW_BOOST_LANGS else "^20"
        lang_fields.append(f"title_txt_{suffix}{boost}")
        lang_fields.append(f"notes_txt_{suffix}{boost}")
        lang_fields.append(f"content_txt_{suffix}")

    return (
        "title^20 subtitle^15 author^80 notes^20 "
        + " ".join(lang_fields)
        + " pub_date enumcron pub_place publisher source_id^10 content"
    )


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
        "first_page_s",
        "last_page_s",
        "pub_place",
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
        "first_page_s": "first_page",
        "last_page_s": "last_page",
        "work_type_s": "work_type",
        "book_journal_s": "book_journal",
        "group_id_s": "group_id",
        "cluster_id_s": "cluster_id",
    }

    keyword_query = None
    within_cluster_id = None

    def __init__(self, solr=None):
        # Create instance copy of return_fields to avoid modifying class variable
        self.return_fields = self.return_fields.copy()

        # Add fields from ALL configured adapters to return_fields
        try:
            from ppa.adapters.loader import get_adapter

            adapters_dir = getattr(settings, "ADAPTERS_DIR", None)
            adapter_names = set()

            if adapters_dir and os.path.exists(adapters_dir):
                for item in Path(adapters_dir).iterdir():
                    if item.is_dir() and (item / "adapter.yaml").exists():
                        adapter_names.add(item.name)

            global_adapter_name = getattr(settings, "ARCHIVE_ADAPTER", None)
            if global_adapter_name:
                adapter_names.add(global_adapter_name)

            for adapter_name in adapter_names:
                adapter = get_adapter(adapter_name)
                if adapter and adapter.field_map:
                    for field_name in adapter.field_map.keys():
                        if field_name not in self.return_fields:
                            self.return_fields.append(field_name)
        except Exception:
            pass

        # field aliases: keys return the fields that will be returned
        # from Solr for search page; values provide an aliased name if
        # it should be different than solr index field.
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
        self.keyword_query = query
        # Apply language-aware qf if any adapter declares supported_languages
        if hasattr(self, "raw_params"):
            qf = _build_language_qf()
            if qf:
                self.raw_params.update(keyword_qf=qf)

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

        # NOTE: Role of order here in separating works from pages (works < pages)
        # may need to be revisited eventually.
        collapse_filter = '{!collapse field=%s sort="order asc"}' % collapse_on

        # We can apply collapse here since we need it for default search
        # cluster id corresponds to index id for works not in a cluster,
        # so collapsing by cluster id still includes works with no cluster id
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
        qs_copy = qs_copy.search(combined_query).raw_query_parameters(
            content_query=content_query,
            keyword_query=self.keyword_query,
            work_query=work_query,
        )

        return qs_copy._base_query_opts()

    def _base_query_opts(self):
        # provide access to regular query opts logic, bypassing keyword/join
        return super().query_opts()


class PageSearchQuerySet(AliasedSolrQuerySet):
    # aliases for any fields we want to rename for search and display
    # includes non-renamed fields to push them into the return
    field_aliases = {
        "id": "id",
        "score": "score",
        "order": "order",
        "title": "title",
        "label": "label",
        "source_id": "source_id",
        #        "image_id": "image_id_s",  # no longer needed for Gale?
        "image_url": "image_url_s",
        "group_id": "group_id_s",
        "cluster_id": "cluster_id_s",
    }
