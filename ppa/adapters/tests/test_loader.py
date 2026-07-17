import os
import tempfile
from pathlib import Path

import pytest
import yaml
from django.test import TestCase, override_settings

from ppa.adapters.loader import (
    Adapter,
    AdapterFrontend,
    clear_adapter_cache,
    get_adapter,
    get_adapters_for_work,
    get_primary_adapter_for_work,
    load_adapter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_adapter(directory: Path, data: dict) -> Path:
    """Write an adapter.yaml into *directory* and return the directory path."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "adapter.yaml").write_text(yaml.dump(data), encoding="utf8")
    return directory


MINIMAL_YAML = {
    "name": "test_adapter",
    "display_name": "Test Adapter",
    "field_map": {
        "title": "title",
        "test_field": "metadata.test_value",
    },
}

FULL_YAML = {
    "name": "full_adapter",
    "display_name": "Full Adapter",
    "field_map": {
        "title": "title",
        "full_ingredients": "metadata.ingredients",
        "full_cook_time": "metadata.cook_time",
    },
    "templates_dir": "templates",
    "supported_languages": ["en", "fr"],
    "display_fields": {
        "list_view": [
            {"field": "full_cook_time", "label": "Cook Time"},
        ],
        "detail_view": [
            {"field": "full_cook_time", "label": "Cook Time", "source": "metadata.cook_time"},
            {"field": "full_ingredients", "label": "Ingredients", "source": "metadata.ingredients"},
        ],
    },
    "solr_schema": {
        "fields": [
            {"name": "full_ingredients_exact", "type": "string", "multiValued": True},
        ]
    },
    "frontend": {
        "css": "adapters/full/full.css",
        "js": "adapters/full/full.js",
        "stimulus_controllers": ["full-rating"],
    },
}


# ---------------------------------------------------------------------------
# load_adapter()
# ---------------------------------------------------------------------------

class TestLoadAdapter(TestCase):

    def setUp(self):
        clear_adapter_cache()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmpdir.name)

    def tearDown(self):
        clear_adapter_cache()
        self.tmpdir.cleanup()

    def test_load_minimal(self):
        adapter_dir = _write_adapter(self.base / "test_adapter", MINIMAL_YAML)
        adapter = load_adapter(str(adapter_dir))

        assert isinstance(adapter, Adapter)
        assert adapter.name == "test_adapter"
        assert adapter.display_name == "Test Adapter"
        assert adapter.field_map == {"title": "title", "test_field": "metadata.test_value"}
        assert adapter.solr_schema is None
        assert adapter.display_fields is None
        assert adapter.frontend is None
        assert adapter.supported_languages is None

    def test_load_full(self):
        adapter_dir = _write_adapter(self.base / "full_adapter", FULL_YAML)
        adapter = load_adapter(str(adapter_dir))

        assert adapter.name == "full_adapter"
        assert adapter.display_name == "Full Adapter"
        assert adapter.supported_languages == ["en", "fr"]
        assert adapter.solr_schema is not None
        assert adapter.display_fields["list_view"][0]["label"] == "Cook Time"

    def test_load_frontend(self):
        adapter_dir = _write_adapter(self.base / "full_adapter", FULL_YAML)
        adapter = load_adapter(str(adapter_dir))

        assert isinstance(adapter.frontend, AdapterFrontend)
        assert adapter.frontend.css == "adapters/full/full.css"
        assert adapter.frontend.js == "adapters/full/full.js"
        assert adapter.frontend.stimulus_controllers == ["full-rating"]

    def test_load_by_absolute_path(self):
        adapter_dir = _write_adapter(self.base / "abs_adapter", MINIMAL_YAML)
        adapter = load_adapter(str(adapter_dir))
        assert adapter.name == "test_adapter"

    def test_missing_adapter_yaml_raises(self):
        empty_dir = self.base / "empty"
        empty_dir.mkdir()
        with pytest.raises(FileNotFoundError, match="adapter.yaml not found"):
            load_adapter(str(empty_dir))

    def test_missing_field_map_raises(self):
        bad_yaml = {"name": "bad", "display_name": "Bad"}
        adapter_dir = _write_adapter(self.base / "bad_adapter", bad_yaml)
        with pytest.raises(RuntimeError, match="field_map"):
            load_adapter(str(adapter_dir))

    def test_field_map_must_be_dict(self):
        bad_yaml = {"name": "bad", "display_name": "Bad", "field_map": ["not", "a", "dict"]}
        adapter_dir = _write_adapter(self.base / "bad_adapter2", bad_yaml)
        with pytest.raises(RuntimeError, match="field_map"):
            load_adapter(str(adapter_dir))

    def test_name_defaults_to_directory_name(self):
        data = dict(MINIMAL_YAML)
        del data["name"]
        adapter_dir = _write_adapter(self.base / "my_adapter_dir", data)
        adapter = load_adapter(str(adapter_dir))
        assert adapter.name == "my_adapter_dir"

    def test_templates_dir_resolved_to_absolute(self):
        adapter_dir = _write_adapter(self.base / "tmpl_adapter", MINIMAL_YAML)
        adapter = load_adapter(str(adapter_dir))
        assert os.path.isabs(adapter.templates_dir)

    def test_source_path_set(self):
        adapter_dir = _write_adapter(self.base / "src_adapter", MINIMAL_YAML)
        adapter = load_adapter(str(adapter_dir))
        assert str(adapter_dir) == adapter.source_path


# ---------------------------------------------------------------------------
# get_adapter() — by name via ADAPTERS_DIR
# ---------------------------------------------------------------------------

class TestGetAdapter(TestCase):

    def setUp(self):
        clear_adapter_cache()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmpdir.name)
        _write_adapter(self.base / "cookbook", MINIMAL_YAML)

    def tearDown(self):
        clear_adapter_cache()
        self.tmpdir.cleanup()

    @override_settings(ADAPTERS_DIR=None, ARCHIVE_ADAPTER=None)
    def test_returns_none_when_not_configured(self):
        assert get_adapter() is None

    def test_get_by_name(self):
        with override_settings(ADAPTERS_DIR=str(self.base)):
            adapter = get_adapter("cookbook")
        assert adapter is not None
        assert adapter.name == "test_adapter"

    def test_get_global_adapter_from_settings(self):
        with override_settings(ADAPTERS_DIR=str(self.base), ARCHIVE_ADAPTER="cookbook"):
            adapter = get_adapter()
        assert adapter is not None

    def test_nonexistent_adapter_returns_none(self):
        with override_settings(ADAPTERS_DIR=str(self.base)):
            adapter = get_adapter("does_not_exist")
        assert adapter is None

    def test_caching(self):
        with override_settings(ADAPTERS_DIR=str(self.base)):
            a1 = get_adapter("cookbook")
            a2 = get_adapter("cookbook")
        assert a1 is a2

    def test_clear_adapter_cache(self):
        with override_settings(ADAPTERS_DIR=str(self.base)):
            a1 = get_adapter("cookbook")
            clear_adapter_cache()
            a2 = get_adapter("cookbook")
        assert a1 is not a2


# ---------------------------------------------------------------------------
# get_adapters_for_work() and get_primary_adapter_for_work()
# ---------------------------------------------------------------------------

class TestGetAdaptersForWork(TestCase):

    def setUp(self):
        clear_adapter_cache()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmpdir.name)
        _write_adapter(self.base / "cookbook", MINIMAL_YAML)
        _write_adapter(self.base / "scifi", {**MINIMAL_YAML, "name": "scifi"})

    def tearDown(self):
        clear_adapter_cache()
        self.tmpdir.cleanup()

    def _make_work(self, collection_adapter_names):
        """Return a mock work whose collections have the given adapter_names."""
        class FakeCollection:
            def __init__(self, name):
                self.adapter_name = name

        class FakeCollectionManager:
            def __init__(self, names):
                self._items = [FakeCollection(n) for n in names]
            def all(self):
                return self._items

        class FakeWork:
            def __init__(self, names):
                self.collections = FakeCollectionManager(names)

        return FakeWork(collection_adapter_names)

    def test_no_collections_falls_back_to_global(self):
        work = self._make_work([])
        with override_settings(ADAPTERS_DIR=str(self.base), ARCHIVE_ADAPTER="cookbook"):
            adapters = get_adapters_for_work(work)
        assert len(adapters) == 1
        assert adapters[0].name == "test_adapter"

    def test_no_collections_no_global_returns_empty(self):
        work = self._make_work([])
        with override_settings(ADAPTERS_DIR=str(self.base), ARCHIVE_ADAPTER=None):
            adapters = get_adapters_for_work(work)
        assert adapters == []

    def test_collection_with_adapter(self):
        work = self._make_work(["cookbook"])
        with override_settings(ADAPTERS_DIR=str(self.base)):
            adapters = get_adapters_for_work(work)
        assert len(adapters) == 1
        assert adapters[0].name == "test_adapter"

    def test_collection_without_adapter_name(self):
        work = self._make_work([""])
        with override_settings(ADAPTERS_DIR=str(self.base), ARCHIVE_ADAPTER=None):
            adapters = get_adapters_for_work(work)
        assert adapters == []

    def test_multiple_collections(self):
        work = self._make_work(["cookbook", "scifi"])
        with override_settings(ADAPTERS_DIR=str(self.base)):
            adapters = get_adapters_for_work(work)
        assert len(adapters) == 2

    def test_get_primary_adapter(self):
        work = self._make_work(["cookbook"])
        with override_settings(ADAPTERS_DIR=str(self.base)):
            primary = get_primary_adapter_for_work(work)
        assert primary is not None
        assert primary.name == "test_adapter"

    def test_get_primary_adapter_no_collections_returns_none(self):
        work = self._make_work([])
        with override_settings(ADAPTERS_DIR=str(self.base), ARCHIVE_ADAPTER=None):
            primary = get_primary_adapter_for_work(work)
        assert primary is None


# ---------------------------------------------------------------------------
# AdapterFrontend dataclass
# ---------------------------------------------------------------------------

class TestAdapterFrontend(TestCase):

    def test_defaults_all_none(self):
        fe = AdapterFrontend()
        assert fe.css is None
        assert fe.js is None
        assert fe.stimulus_controllers is None

    def test_partial_init(self):
        fe = AdapterFrontend(css="style.css")
        assert fe.css == "style.css"
        assert fe.js is None

    def test_full_init(self):
        fe = AdapterFrontend(css="a.css", js="b.js", stimulus_controllers=["c1", "c2"])
        assert fe.stimulus_controllers == ["c1", "c2"]


# ---------------------------------------------------------------------------
# Integration: load real cookbook adapter
# ---------------------------------------------------------------------------

class TestRealCookbookAdapter(TestCase):
    """Load the actual cookbook adapter from examples/adapters/."""

    def setUp(self):
        clear_adapter_cache()

    def tearDown(self):
        clear_adapter_cache()

    def test_load_cookbook_adapter(self):
        from django.conf import settings
        adapters_dir = getattr(settings, "ADAPTERS_DIR", None)
        if not adapters_dir:
            self.skipTest("ADAPTERS_DIR not configured")

        cookbook_dir = Path(adapters_dir) / "cookbook"
        if not cookbook_dir.exists():
            self.skipTest("cookbook adapter not found in ADAPTERS_DIR")

        adapter = load_adapter(str(cookbook_dir))
        assert adapter.name == "cookbook"
        assert "cookbook_ingredients" in adapter.field_map
        assert "cookbook_cook_time" in adapter.field_map
        assert adapter.supported_languages == ["en"]
        assert adapter.display_fields is not None
        assert "list_view" in adapter.display_fields
        assert "detail_view" in adapter.display_fields

    def test_cookbook_display_fields_structure(self):
        from django.conf import settings
        adapters_dir = getattr(settings, "ADAPTERS_DIR", None)
        if not adapters_dir:
            self.skipTest("ADAPTERS_DIR not configured")

        cookbook_dir = Path(adapters_dir) / "cookbook"
        if not cookbook_dir.exists():
            self.skipTest("cookbook adapter not found in ADAPTERS_DIR")

        adapter = load_adapter(str(cookbook_dir))
        detail = adapter.display_fields["detail_view"]
        passage_fields = [f for f in detail if f.get("type") == "passage"]
        assert len(passage_fields) == 1
        assert passage_fields[0]["field"] == "cookbook_passage"

    def test_scifi_adapter(self):
        from django.conf import settings
        adapters_dir = getattr(settings, "ADAPTERS_DIR", None)
        if not adapters_dir:
            self.skipTest("ADAPTERS_DIR not configured")

        scifi_dir = Path(adapters_dir) / "scifi"
        if not scifi_dir.exists():
            self.skipTest("scifi adapter not found in ADAPTERS_DIR")

        adapter = load_adapter(str(scifi_dir))
        assert adapter.name == "scifi"
        assert "scifi_rating_score" in adapter.field_map
