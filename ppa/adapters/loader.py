from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from django.conf import settings

logger = logging.getLogger(__name__)

# Model fields that are valid top-level field_map targets (i.e. direct
# attributes on DigitizedWork, not stored in metadata).
_DIGITIZED_WORK_FIELDS = frozenset(
    [
        "title",
        "subtitle",
        "sort_title",
        "author",
        "pub_date",
        "pub_place",
        "publisher",
        "enumcron",
        "source_id",
        "source_url",
        "record_id",
        "notes",
        "public_notes",
        "book_journal",
        "pages_orig",
        "pages_digital",
        "item_type",
    ]
)


@dataclass
class AdapterFrontend:
    """Frontend asset configuration declared in adapter.yaml under `frontend:`."""

    css: Optional[str] = None
    js: Optional[str] = None
    stimulus_controllers: Optional[List[str]] = None


@dataclass
class Adapter:
    name: str
    display_name: str
    field_map: Dict[str, str]
    templates_dir: str
    solr_schema: Optional[Dict]
    source_path: str
    display_fields: Optional[Dict] = None
    frontend: Optional[AdapterFrontend] = None
    supported_languages: Optional[List[str]] = None


_ADAPTER_CACHE: Dict[str, Adapter] = {}


def _resolve_adapter_path(path_or_name: str) -> Path:
    p = Path(path_or_name)
    if p.exists() and p.is_dir():
        return p
    base = getattr(settings, "ADAPTERS_DIR", None)
    if not base:
        raise RuntimeError("ADAPTERS_DIR is not configured in settings")
    candidate = Path(base) / path_or_name
    if candidate.exists() and candidate.is_dir():
        return candidate
    raise FileNotFoundError(f"Adapter directory not found: {path_or_name}")


def _validate_field_map(field_map: dict, adapter_name: str) -> None:
    """Validate field_map values are valid DigitizedWork paths.

    Each value must be either:
    - a direct model field name (e.g. ``title``, ``author``)
    - a ``metadata.<key>`` dotted path (e.g. ``metadata.cook_time``)

    Raises :exc:`RuntimeError` listing all invalid paths.
    """
    invalid = []
    for solr_field, model_path in field_map.items():
        if not isinstance(model_path, str):
            invalid.append(
                f"  {solr_field!r}: value must be a string, got {type(model_path).__name__}"
            )
            continue
        parts = model_path.split(".", 1)
        if parts[0] == "metadata":
            if len(parts) < 2 or not parts[1]:
                invalid.append(
                    f"  {solr_field!r}: 'metadata.' must be followed by a key name"
                )
        elif parts[0] not in _DIGITIZED_WORK_FIELDS:
            invalid.append(
                f"  {solr_field!r}: '{model_path}' is not a recognised DigitizedWork field "
                f"(use 'metadata.<key>' for custom fields)"
            )
    if invalid:
        raise RuntimeError(
            f"adapter '{adapter_name}' has invalid field_map entries:\n" + "\n".join(invalid)
        )


def _validate_solr_schema(solr_schema: dict, adapter_name: str) -> None:
    """Validate solr_schema structure.

    Each field entry must have a ``name`` and a ``type``.
    Field names must not collide with core PPA schema fields.

    Raises :exc:`RuntimeError` on structural problems.
    """
    if not isinstance(solr_schema, dict):
        raise RuntimeError(
            f"adapter '{adapter_name}': solr_schema must be a mapping, "
            f"got {type(solr_schema).__name__}"
        )
    fields = solr_schema.get("fields", [])
    if not isinstance(fields, list):
        raise RuntimeError(
            f"adapter '{adapter_name}': solr_schema.fields must be a list"
        )

    _CORE_SOLR_FIELDS = frozenset([
        "id", "title", "author", "pub_date", "pub_place", "publisher",
        "source_id", "source_url", "content", "label", "order",
        "item_type", "group_id_s", "cluster_id_s", "last_modified",
    ])

    errors = []
    for i, field in enumerate(fields):
        if not isinstance(field, dict):
            errors.append(f"  fields[{i}]: must be a mapping")
            continue
        if "name" not in field:
            errors.append(f"  fields[{i}]: missing required 'name'")
        if "type" not in field:
            errors.append(f"  fields[{i}]: missing required 'type'")
        name = field.get("name", "")
        if name in _CORE_SOLR_FIELDS:
            errors.append(
                f"  fields[{i}]: '{name}' conflicts with a core PPA Solr field"
            )
    if errors:
        raise RuntimeError(
            f"adapter '{adapter_name}' has invalid solr_schema:\n" + "\n".join(errors)
        )


def load_adapter(path_or_name: str) -> Adapter:
    """Load and validate an adapter by directory name or path."""
    adapter_dir = _resolve_adapter_path(path_or_name)
    adapter_yaml = adapter_dir / "adapter.yaml"
    if not adapter_yaml.exists():
        raise FileNotFoundError(f"adapter.yaml not found in {adapter_dir}")
    with adapter_yaml.open("r", encoding="utf8") as fh:
        data = yaml.safe_load(fh) or {}

    name = data.get("name") or adapter_dir.name
    display_name = data.get("display_name", name)
    field_map = data.get("field_map")
    if not isinstance(field_map, dict):
        raise RuntimeError("adapter.yaml must include a dictionary 'field_map'")
    _validate_field_map(field_map, name)

    templates_dir = data.get("templates_dir", "templates")
    templates_path = str(adapter_dir / templates_dir)
    solr_schema = data.get("solr_schema")
    if solr_schema is not None:
        _validate_solr_schema(solr_schema, name)
    display_fields = data.get("display_fields")
    supported_languages = data.get("supported_languages") or None

    frontend = None
    frontend_data = data.get("frontend")
    if isinstance(frontend_data, dict):
        frontend = AdapterFrontend(
            css=frontend_data.get("css"),
            js=frontend_data.get("js"),
            stimulus_controllers=frontend_data.get("stimulus_controllers"),
        )

    return Adapter(
        name=name,
        display_name=display_name,
        field_map=field_map,
        templates_dir=templates_path,
        solr_schema=solr_schema,
        source_path=str(adapter_dir),
        display_fields=display_fields,
        frontend=frontend,
        supported_languages=supported_languages,
    )


def get_adapter(adapter_name: Optional[str] = None) -> Optional[Adapter]:
    """Get adapter by name. If no name provided, returns global adapter from settings."""
    global _ADAPTER_CACHE

    if adapter_name is None:
        adapter_name = getattr(settings, "ARCHIVE_ADAPTER", None)
        if not adapter_name:
            return None

    if adapter_name in _ADAPTER_CACHE:
        return _ADAPTER_CACHE[adapter_name]

    try:
        adapter = load_adapter(adapter_name)
        _ADAPTER_CACHE[adapter_name] = adapter
        return adapter
    except Exception as err:
        logger.exception("Failed to load adapter '%s': %s", adapter_name, err)
        return None


def get_adapters_for_work(work) -> List[Adapter]:
    """Get all adapters applicable to a work based on its collections."""
    adapters = []
    adapter_names = set()

    for collection in work.collections.all():
        if collection.adapter_name:
            adapter_names.add(collection.adapter_name)

    if not adapter_names:
        global_adapter = get_adapter()
        if global_adapter:
            return [global_adapter]
        return []

    for name in adapter_names:
        adapter = get_adapter(name)
        if adapter:
            adapters.append(adapter)

    return adapters


def get_primary_adapter_for_work(work) -> Optional[Adapter]:
    """Get the primary (first) adapter for a work."""
    adapters = get_adapters_for_work(work)
    return adapters[0] if adapters else None


def clear_adapter_cache():
    """Clear the adapter cache. Useful for testing."""
    global _ADAPTER_CACHE
    _ADAPTER_CACHE = {}
