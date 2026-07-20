"""
**update_solr_schema** applies adapter field definitions to the live Solr
schema via the Solr Schema API, so new adapter fields can be searched and
returned without manually editing ``managed-schema.xml``.

Usage::

    # apply fields for a specific adapter
    python manage.py update_solr_schema --adapter ia_prosody

    # apply fields for all adapters found in ADAPTERS_DIR
    python manage.py update_solr_schema --all

    # dry-run: show what would be added without touching Solr
    python manage.py update_solr_schema --adapter scifi --dry-run

The command reads the ``solr_schema.fields`` list from the adapter's
``adapter.yaml`` and issues ``add-field`` (or ``replace-field`` if the
field already exists) requests to the Solr Schema API.

Fields already present in the schema with identical configuration are
silently skipped.  Only fields defined under ``solr_schema.fields`` in the
adapter YAML are processed; dynamic fields and copy fields are not managed
by this command.

Solr connection is taken from ``settings.SOLR_CONNECTIONS['default']``.
"""

import json
import logging
import os

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ppa.adapters.loader import load_adapter, _resolve_adapter_path

logger = logging.getLogger(__name__)

# Solr Schema API default field attributes to include when comparing
_CMP_ATTRS = ("type", "multiValued", "stored", "indexed", "required")


def _solr_schema_url():
    """Return the Solr Schema API URL for the configured collection."""
    conn = getattr(settings, "SOLR_CONNECTIONS", {}).get("default", {})
    base = conn.get("URL", "http://localhost:8983/solr/").rstrip("/")
    collection = conn.get("COLLECTION", "ppa")
    return f"{base}/{collection}/schema"


def _get_existing_fields(schema_url, session):
    """Fetch existing explicit fields from Solr Schema API.

    Returns a dict mapping field name → field config dict.
    """
    resp = session.get(schema_url + "/fields", timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return {f["name"]: f for f in data.get("fields", [])}


def _fields_differ(existing, desired):
    """Return True if *desired* has attributes that differ from *existing*."""
    for attr in _CMP_ATTRS:
        if attr in desired and existing.get(attr) != desired[attr]:
            return True
    return False


def _apply_adapter_schema(adapter_name, dry_run, stdout, style):
    """Load one adapter and apply its solr_schema fields to Solr.

    Returns (added, updated, skipped) counts.
    """
    try:
        adapter = load_adapter(adapter_name)
    except (FileNotFoundError, RuntimeError) as exc:
        raise CommandError(str(exc)) from exc

    if not adapter.solr_schema:
        stdout.write(f"  adapter '{adapter_name}': no solr_schema defined, skipping")
        return 0, 0, 0

    fields = adapter.solr_schema.get("fields", [])
    if not fields:
        stdout.write(f"  adapter '{adapter_name}': solr_schema.fields is empty, skipping")
        return 0, 0, 0

    schema_url = _solr_schema_url()
    session = requests.Session()

    if not dry_run:
        try:
            existing = _get_existing_fields(schema_url, session)
        except requests.RequestException as exc:
            raise CommandError(f"Cannot connect to Solr at {schema_url}: {exc}") from exc
    else:
        existing = {}

    added = updated = skipped = 0
    commands = []

    for field_def in fields:
        name = field_def.get("name", "")
        if not name:
            stdout.write(style.WARNING(f"  skipping field with no name: {field_def}"))
            continue

        if name in existing:
            if _fields_differ(existing[name], field_def):
                action = "replace-field"
                updated += 1
                verb = style.WARNING(f"  UPDATE {name}")
            else:
                skipped += 1
                stdout.write(f"  skip   {name} (unchanged)")
                continue
        else:
            action = "add-field"
            added += 1
            verb = style.SUCCESS(f"  ADD    {name}")

        stdout.write(verb + f" (type={field_def.get('type', '?')})")
        commands.append({action: field_def})

    if commands and not dry_run:
        payload = json.dumps(commands)
        try:
            resp = session.post(
                schema_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise CommandError(f"Solr Schema API error: {exc}") from exc

        # Check for Solr-level errors in the response body
        result = resp.json()
        errors = result.get("errors")
        if errors:
            raise CommandError(f"Solr returned errors: {errors}")

    return added, updated, skipped


class Command(BaseCommand):
    """Apply adapter solr_schema field definitions to the live Solr schema."""

    help = __doc__

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--adapter",
            metavar="NAME",
            help="Name of a single adapter to apply (must exist in ADAPTERS_DIR).",
        )
        group.add_argument(
            "--all",
            action="store_true",
            dest="all_adapters",
            help="Apply schema for all adapters found in ADAPTERS_DIR.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without making any Solr requests.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be made to Solr"))

        if options["adapter"]:
            adapter_names = [options["adapter"]]
        else:
            adapters_dir = getattr(settings, "ADAPTERS_DIR", None)
            if not adapters_dir or not os.path.isdir(adapters_dir):
                raise CommandError(
                    "ADAPTERS_DIR is not set or does not exist; cannot use --all"
                )
            adapter_names = [
                d for d in os.listdir(adapters_dir)
                if os.path.isdir(os.path.join(adapters_dir, d))
                and os.path.exists(os.path.join(adapters_dir, d, "adapter.yaml"))
            ]
            if not adapter_names:
                raise CommandError(f"No adapters found in {adapters_dir}")
            self.stdout.write(f"Found {len(adapter_names)} adapter(s): {', '.join(sorted(adapter_names))}")

        total_added = total_updated = total_skipped = 0
        for name in sorted(adapter_names):
            self.stdout.write(f"\nAdapter: {name}")
            added, updated, skipped = _apply_adapter_schema(
                name, dry_run, self.stdout, self.style
            )
            total_added += added
            total_updated += updated
            total_skipped += skipped

        action_label = "Would apply" if dry_run else "Applied"
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{action_label}: {total_added} added, "
                f"{total_updated} updated, {total_skipped} skipped"
            )
        )
