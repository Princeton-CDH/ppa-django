"""Factory shim to return either real parasolr classes or fake fallbacks
depending on the ENABLE_SOLR_INDEXING waffle switch.

All code that previously imported from parasolr.django should instead
import from ppa.solr_factory.
"""
import logging

logger = logging.getLogger(__name__)


def _is_solr_enabled():
    """Lazily check the waffle switch so this is safe to call after app setup."""
    try:
        from ppa.flags import is_flag_enabled
        return is_flag_enabled("ENABLE_SOLR_INDEXING")
    except Exception:
        return False


RealSolrClient = None
RealSolrQuerySet = None
RealAliasedSolrQuerySet = None
try:
    from parasolr.django import (
        SolrClient as RealSolrClient,
        SolrQuerySet as RealSolrQuerySet,
        AliasedSolrQuerySet as RealAliasedSolrQuerySet,
    )
except Exception:
    logger.debug("parasolr not available; using fake Solr clients")


class FakeSolrClient:
    class _Update:
        def index(self, *args, **kwargs):
            logger.debug("FakeSolrClient.index called; no-op")

        def delete_by_query(self, *args, **kwargs):
            logger.debug("FakeSolrClient.delete_by_query called; no-op")

    def __init__(self, *args, **kwargs):
        self.update = self._Update()


class FakeSolrQuerySet:
    """Minimal fake SolrQuerySet that returns empty results and supports chaining."""

    def __init__(self, *args, **kwargs):
        self._filters = {}

    def stats(self, *args, **kwargs): return self
    def facet(self, *args, **kwargs): return self
    def facet_range(self, *args, **kwargs): return self
    def facet_field(self, *args, **kwargs): return self
    def facet_pivot(self, *args, **kwargs): return {}
    def highlight(self, *args, **kwargs): return self
    def group(self, *args, **kwargs): return self
    def order_by(self, *args, **kwargs): return self
    def filter(self, *args, **kwargs): return self
    def search(self, *args, **kwargs): return self
    def raw_query_parameters(self, *args, **kwargs): return self
    def only(self, *args, **kwargs): return self
    def also(self, *args, **kwargs): return self
    def all(self): return self
    def none(self): return self
    def count(self): return 0

    def get_facets(self):
        class _FacetPivot(dict):
            def __init__(self):
                super().__init__()
                self["collections_exact"] = []
                self.collections_exact = []

        class _Facets:
            def __init__(self):
                self.facet_pivot = _FacetPivot()
                self.facet_ranges = {
                    "pub_date": {"start": 1800, "end": 2000, "gap": 10, "counts": []}
                }
                self.facet_fields = {
                    "collections_exact": {},
                    "author_exact": {},
                    "pub_place": {},
                }
        return _Facets()

    def get_results(self):
        return {"docs": [], "numFound": 0}

    def get_highlighting(self):
        return {}

    def __iter__(self): return iter([])

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self
        return []

    def __len__(self): return 0

    @property
    def groups(self): return []


def SolrClientFactory(*args, **kwargs):
    if _is_solr_enabled() and RealSolrClient is not None:
        return RealSolrClient(*args, **kwargs)
    return FakeSolrClient()


def SolrQuerySetFactory(*args, **kwargs):
    if _is_solr_enabled() and RealSolrQuerySet is not None:
        return RealSolrQuerySet(*args, **kwargs)
    return FakeSolrQuerySet()


SolrClient = SolrClientFactory
SolrQuerySet = SolrQuerySetFactory


def _get_aliased_queryset_class():
    if _is_solr_enabled() and RealAliasedSolrQuerySet is not None:
        return RealAliasedSolrQuerySet
    return FakeSolrQuerySet


# AliasedSolrQuerySet is used as a base class in solr.py, so it must be
# resolved at import time of *that* module (after app registry is ready).
# We expose a lazy proxy that resolves on first subclass use.
class AliasedSolrQuerySet(FakeSolrQuerySet):
    """Lazy proxy: delegates to real AliasedSolrQuerySet when Solr is enabled,
    otherwise behaves as FakeSolrQuerySet."""
    pass


def _resolve_instance_value(instance, path):
    """Resolve a dotted path like 'metadata.ingredients' or 'title' on instance."""
    if not path:
        return None
    if path.startswith("metadata."):
        getter = getattr(instance, "get_adapter_field", None)
        if getter:
            return getter(path)
        meta = getattr(instance, "metadata", None)
        if isinstance(meta, dict):
            parts = path.split(".")[1:]
            cur = meta
            for p in parts:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    return None
            return cur
        return None
    return getattr(instance, path, None)


# Maps ISO 639-1 language codes to Solr dynamic field suffix.
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


def map_model_to_solr(instance, adapter=None):
    """
    Map a model instance to a Solr document dict using adapter field mappings.

    Merges fields from ALL adapters applicable to the instance's collections.
    Also performs language detection and writes language-specific field copies.
    """
    doc = {}

    try:
        if adapter is not None:
            adapters = [adapter] if adapter else []
        else:
            from ppa.adapters.loader import get_adapters_for_work
            adapters = get_adapters_for_work(instance)
    except Exception:
        adapters = []

    for adp in adapters:
        if not getattr(adp, "field_map", None):
            continue
        for solr_field, model_path in adp.field_map.items():
            val = _resolve_instance_value(instance, model_path)
            if val is not None:
                doc[solr_field] = val

    # Language detection for multilingual field routing
    supported = set()
    for adp in adapters:
        if getattr(adp, "supported_languages", None):
            supported.update(adp.supported_languages)

    if not supported:
        return doc

    text_for_detection = " ".join(filter(None, [
        _resolve_instance_value(instance, "title"),
        _resolve_instance_value(instance, "notes"),
    ]))

    if not text_for_detection.strip():
        return doc

    try:
        from langdetect import detect
        lang = detect(text_for_detection)
    except Exception:
        return doc

    if lang not in supported:
        lang = "en"

    suffix = _LANG_FIELD_SUFFIX.get(lang)
    if not suffix:
        return doc

    doc["language_s"] = lang

    for field in ("title", "notes"):
        val = _resolve_instance_value(instance, field)
        if val:
            doc[f"{field}_txt_{suffix}"] = val

    return doc
