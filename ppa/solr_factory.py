"""Factory shim to return either real parasolr classes or fake fallbacks
depending on settings.ENABLE_SOLR_INDEXING.

Patch points in code should import from `ppa.solr_factory` instead of
`parasolr.django` so behavior can be toggled at runtime.
"""
import logging
from ppa.flags import is_flag_enabled

logger = logging.getLogger(__name__)

# Evaluate whether Solr is enabled via waffle/switches or settings
ENABLE_SOLR = is_flag_enabled("ENABLE_SOLR_INDEXING")

# Attempt to import real parasolr classes under distinct names to avoid
# redefinition issues when we expose factory names below.
RealSolrClient = None
RealSolrQuerySet = None
RealAliasedSolrQuerySet = None
if ENABLE_SOLR:
    try:
        from parasolr.django import (
            SolrClient as RealSolrClient,
            SolrQuerySet as RealSolrQuerySet,
            AliasedSolrQuerySet as RealAliasedSolrQuerySet,
        )
    except Exception:
        logger.exception("Failed to import parasolr; falling back to fake clients")
        ENABLE_SOLR = False


class FakeSolrClient:
    class _Update:
        def index(self, *args, **kwargs):
            logger.debug("FakeSolrClient.index called; no-op")

        def delete_by_query(self, *args, **kwargs):
            logger.debug("FakeSolrClient.delete_by_query called; no-op")

    def __init__(self, *args, **kwargs):
        self.update = self._Update()


class FakeSolrQuerySet:
    def __init__(self, *args, **kwargs):
        self._filters = {}

    def stats(self, *args, **kwargs):
        return self

    def facet(self, *args, **kwargs):
        return self

    def facet_pivot(self, *args, **kwargs):
        return {}

    def get_facets(self):
        # return minimal object with facet_pivot attribute used in Collection.stats
        class _F:
            facet_pivot = type("P", (), {"collections_exact": []})

        return _F()

    def all(self):
        return self

    def count(self):
        return 0

    def none(self):
        return self


def SolrClientFactory(*args, **kwargs):
    if ENABLE_SOLR and RealSolrClient is not None:
        return RealSolrClient(*args, **kwargs)
    return FakeSolrClient()


def SolrQuerySetFactory(*args, **kwargs):
    if ENABLE_SOLR and RealSolrQuerySet is not None:
        return RealSolrQuerySet(*args, **kwargs)
    return FakeSolrQuerySet()


# Export names for backward-compatible imports
SolrClient = SolrClientFactory
SolrQuerySet = SolrQuerySetFactory
if ENABLE_SOLR and RealAliasedSolrQuerySet is not None:
    AliasedSolrQuerySet = RealAliasedSolrQuerySet
else:
    AliasedSolrQuerySet = FakeSolrQuerySet
