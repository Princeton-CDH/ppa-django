# How to Add a New Data Source Adapter

This guide walks through adding a new data source to ppa-reuse from scratch. The
`ia_prosody` adapter (historical English prosody texts from the Internet Archive) is
used as the worked example throughout. By the end you will have a working adapter that
imports metadata, indexes full text, and displays custom fields in the archive UI.

Target reader: a DH developer who has the project running locally but has never touched
the adapter system before.

---

## 1. Prerequisites

You need the project running before starting. If you haven't done that yet:

```bash
devbox shell          # activates the devbox environment
devbox run setup      # creates .venv, installs deps, starts Docker, runs migrations
devbox run dev        # starts Postgres + Solr via Docker, then runs the dev server
```

Verify the services are healthy before continuing:

- Django dev server: http://localhost:8000/
- Solr admin: http://localhost:8983/solr/#/ppa

`devbox run dev` will refuse to start the server if Solr isn't reachable, so a
successful startup is a good sign.

---

## 2. Create the adapter directory

Adapters live under `examples/adapters/` by default. The directory name is the adapter
name — it is used in management commands and in the `ARCHIVE_ADAPTER` setting.

```bash
mkdir examples/adapters/my_adapter
```

You can put adapters anywhere on disk by setting `ADAPTERS_DIR` in the environment (see
step 5). The default is `<project-root>/examples/adapters/`.

The only required file in the directory is `adapter.yaml`. Everything else
(templates, static files, import CSVs) is optional and referenced from inside the YAML.

For the ia_prosody example the layout is:

```
examples/adapters/ia_prosody/
    adapter.yaml
    ia_prosody_import.csv
    ia_prosody_works.json   # static snapshot, not used by Django
    README.md
```

---

## 3. Write `adapter.yaml`

This is the heart of the adapter. Here is the complete `ia_prosody` file followed by an
explanation of every key.

```yaml
name: ia_prosody
display_name: "Internet Archive — English Prosody"
description: >
  Historical English-language texts on prosody, versification, and the study
  of poetic meter, sourced from the Internet Archive (archive.org).
  Covers works from the early 1800s through the early 1900s, all in the
  public domain and carrying machine-readable OCR text.

supported_languages:
  - en

field_map:
  title: title
  author: author
  pub_date: pub_date
  pub_place: pub_place
  publisher: publisher
  ia_prosody_ia_id: metadata.ia_id
  ia_prosody_subject: metadata.subject
  ia_prosody_description: metadata.description
  ia_prosody_ia_url: metadata.ia_url

display_fields:
  list_view:
    - field: ia_prosody_subject
      label: "Subject"
    - field: pub_place
      label: "Place of Publication"
  detail_view:
    - field: ia_prosody_subject
      label: "Subject"
      source: "metadata.subject"
    - field: ia_prosody_description
      label: "Description"
      source: "metadata.description"
    - field: ia_prosody_ia_url
      label: "Internet Archive"
      source: "metadata.ia_url"

solr_schema:
  fields:
    - name: ia_prosody_subject_exact
      type: string
      multiValued: true
```

### Key-by-key reference

**`name`**
The machine identifier. Must match the directory name exactly. Used in management
commands (`--adapter ia_prosody`) and in the `ARCHIVE_ADAPTER` env var.

**`display_name`**
Human-readable name shown in the UI.

**`supported_languages`**
List of ISO 639-1 language codes. Used for language-based filtering when relevant.
Omit the key entirely if you don't want language filtering.

**`field_map`**
Maps Solr field names to Django model paths. There are two kinds of target:

- **Direct model field** — a field that exists as a column on `DigitizedWork`
  (e.g. `title`, `author`, `pub_date`, `pub_place`, `publisher`). The full list of
  valid direct fields is in `ppa/adapters/loader.py` under `_DIGITIZED_WORK_FIELDS`.
- **`metadata.<key>`** — stored in the `DigitizedWork.metadata` JSONField. Use this
  for any field that is specific to your data source and does not belong in the core
  model. The key name is arbitrary; by convention prefix it with the adapter name to
  avoid collisions (e.g. `metadata.ia_id`, `metadata.subject`).

The left-hand side (the Solr field name) can be anything, but again use an adapter
prefix for custom fields to avoid collisions with core PPA Solr fields (`id`, `title`,
`author`, `pub_date`, `source_id`, `content`, etc.).

**`display_fields`**
Controls which fields appear in the archive list and detail views.

- `list_view`: a list of `{field, label}` objects. `field` is the Solr field name from
  your `field_map`. These appear as metadata chips/lines on search result cards.
- `detail_view`: a list of `{field, label, source}` objects. `source` is the
  `metadata.<key>` path used to read the value from the database object (not from
  Solr). Include `source` whenever the field is stored in `metadata`.

**`solr_schema`**
Declares any additional Solr fields that need to be added to the schema. Each entry
requires at minimum `name` and `type`. Optional Solr attributes like `multiValued`,
`stored`, `indexed`, and `required` can also be set.

You only need to list fields here if you need Solr to handle them differently from the
default dynamic field rules — for example, an exact-match string field for faceting.
Fields already handled by dynamic field patterns in the Solr config do not need an
explicit entry here.

You must not use any name that conflicts with a core PPA Solr field. The loader will
raise a `RuntimeError` at startup if it detects a collision.

**`templates_dir`**
Path to a templates directory relative to the adapter directory. Defaults to
`templates`. When `ARCHIVE_ADAPTER` is set, Django prepends this directory to
`TEMPLATES[0]["DIRS"]` so adapter templates take priority over the project defaults
(see step 11).

**`frontend`**
Optional. Declares adapter-specific CSS, JS, and Stimulus controllers:

```yaml
frontend:
  css: static/css/my_adapter.css
  js: static/js/my_adapter.js
  stimulus_controllers:
    - my-controller
```

Paths are relative to the adapter directory. Static files are served under
`/static/adapters/<adapter-name>/`.

---

## 4. Apply the Solr schema

If your `adapter.yaml` defines `solr_schema.fields`, you need to register those fields
with Solr before indexing.

First do a dry run to see what would change:

```bash
python manage.py update_solr_schema --adapter ia_prosody --dry-run
```

Expected output:

```
DRY RUN — no changes will be made to Solr

Adapter: ia_prosody
  ADD    ia_prosody_subject_exact (type=string)

Would apply: 1 added, 0 updated, 0 skipped
```

If the output looks right, apply it for real:

```bash
python manage.py update_solr_schema --adapter ia_prosody
```

To apply all adapters in `ADAPTERS_DIR` at once, use `--all` instead of `--adapter`.

The command issues `add-field` or `replace-field` requests to the Solr Schema API.
Fields that already exist with identical config are silently skipped, so it is safe to
re-run.

---

## 5. Set environment variables

Two environment variables control which adapter is active:

| Variable | Purpose | Default |
|---|---|---|
| `ADAPTERS_DIR` | Directory that contains adapter subdirectories | `<project-root>/examples/adapters` |
| `ARCHIVE_ADAPTER` | Name of the active adapter (directory name) | unset |

For local development you can export them in your shell or add them to a `.env` file:

```bash
export ADAPTERS_DIR=/path/to/your/adapters   # only needed if not using examples/adapters/
export ARCHIVE_ADAPTER=ia_prosody
```

When `ARCHIVE_ADAPTER` is set, Django automatically:
- Prepends the adapter's `templates_dir` to the template search path
- Adds the adapter's `static/` directory to `STATICFILES_DIRS`

If `ARCHIVE_ADAPTER` is not set, the adapter system still works for import and
indexing; the UI just uses default templates.

---

## 6. Enable waffle switches

The Internet Archive source type is gated behind a waffle feature switch. You must
enable it before importing IA content.

```bash
python manage.py shell -c "
from waffle.models import Switch
Switch.objects.update_or_create(
    name='enable_internet_archive',
    defaults={'active': True}
)
print('enable_internet_archive: ON')
"
```

Other switches you may want to enable during development:

| Switch | Purpose |
|---|---|
| `enable_solr_indexing` | Enables Solr indexing (required for search to work) |
| `enable_internet_archive` | Enables the IA source type |
| `enable_hathi` | Enables HathiTrust source type |
| `enable_corppa` | Enables corppa integration |

`devbox run dev` enables `enable_solr_indexing` automatically on startup.

---

## 7. Import data

For the ia_prosody adapter, import from the bundled CSV:

```bash
python manage.py ia_import -c examples/adapters/ia_prosody/ia_prosody_import.csv
```

The CSV must have at minimum an `id` column containing IA identifiers. An optional
`notes` column is imported as private notes on the record.

You can also import specific items by identifier without a CSV:

```bash
python manage.py ia_import scienceofenglish00laniuoft orthometrytreati00brewrich
```

The command fetches metadata from `https://archive.org/metadata/{identifier}` and
downloads the best available full-text file (DjVu XML preferred, then hOCR, then plain
text). Items already in the database are skipped automatically.

At the end of a successful import run you will see a summary like:

```
Processed 10 items.
Imported 10; skipped 0; 0 errors; 0 invalid ids.
```

---

## 8. Index works

Index the work-level records into Solr:

```bash
python manage.py index -i work
```

This indexes metadata for all `DigitizedWork` objects. The `-i work` flag limits
indexing to works only (not pages).

---

## 9. Index pages

Index the full-text page content:

```bash
python manage.py index_pages
```

This is a multiprocessing command. By default it uses all available CPU cores. To limit
concurrency:

```bash
python manage.py index_pages --processes 2
```

Page indexing can take a while for large corpora. For the ia_prosody set (10 items) it
completes in under a minute.

---

## 10. Verify in the browser

With the dev server running (`devbox run dev`), go to http://localhost:8000/archive/

You should see:
- Search results with your imported works
- Metadata fields defined in `display_fields.list_view` appearing on search result cards
- Clicking a result shows the detail view with fields from `display_fields.detail_view`
- Full-text search working across page content (requires page indexing from step 9)

If works appear but pages don't search, check that `enable_solr_indexing` is on and
that `index_pages` completed without errors.

---

## 11. Template overrides

The adapter can override any project template by providing a file at the same relative
path inside the adapter's `templates_dir`.

For example, to customise the work detail page for ia_prosody:

```
examples/adapters/ia_prosody/
    templates/
        archive/
            digitizedwork_detail.html
```

Because the adapter templates directory is prepended to Django's template search path
(when `ARCHIVE_ADAPTER` is set), `digitizedwork_detail.html` in the adapter will be
found before the project-level version.

This works for any template in the project. Common candidates to override:
- `archive/digitizedwork_detail.html` — work detail page
- `archive/search.html` — search results page
- `base.html` — global layout, header, footer

You do not need to copy the entire template; use `{% extends %}` and `{% block %}` to
override only the parts you need:

```html
{% extends "archive/digitizedwork_detail.html" %}

{% block extra_metadata %}
  {# Add adapter-specific metadata here #}
{% endblock %}
```

---

## 12. Troubleshooting

### Solr not running

```
CommandError: Cannot connect to Solr at http://localhost:8983/solr/ppa/schema
```

Start the Docker services:

```bash
docker compose -f docker/docker-compose.dev.yml up -d db solr
```

Then wait for Solr to be ready (`bash scripts/wait_for_solr.sh`) before retrying.

### Adapter not found

```
RuntimeError: ADAPTERS_DIR is not configured in settings
# or
FileNotFoundError: Adapter directory not found: my_adapter
```

Check that:
1. `ADAPTERS_DIR` points to a directory that exists on disk
2. The adapter subdirectory name matches what you pass to `--adapter` / `ARCHIVE_ADAPTER`
3. The subdirectory contains an `adapter.yaml` file

### `field_map` validation error

```
RuntimeError: adapter 'my_adapter' has invalid field_map entries:
  'my_field': 'bad_path' is not a recognised DigitizedWork field
  (use 'metadata.<key>' for custom fields)
```

The right-hand side of each `field_map` entry must be either:
- A direct `DigitizedWork` model field (see `_DIGITIZED_WORK_FIELDS` in
  `ppa/adapters/loader.py` for the full list)
- A `metadata.<key>` dotted path

If your field is data-source specific, use `metadata.my_key` instead of a bare name.

### `solr_schema` conflict

```
RuntimeError: adapter 'my_adapter' has invalid solr_schema:
  fields[0]: 'title' conflicts with a core PPA Solr field
```

Rename your field. Core PPA fields (`id`, `title`, `author`, `pub_date`, `source_id`,
`content`, and others) cannot be redefined by an adapter. Use an adapter-prefixed name
like `my_adapter_title_variant`.

### Import skipped all items

```
Processed 10 items.
Imported 0; skipped 10; 0 errors; 0 invalid ids.
```

The items are already in the database. If you want to re-import from scratch, delete
them first via the Django admin at http://localhost:8000/admin/archive/digitizedwork/
or via the shell:

```python
from ppa.archive.models import DigitizedWork
DigitizedWork.objects.filter(source=DigitizedWork.INTERNET_ARCHIVE).delete()
```

### Works appear in admin but not in search

Ensure both `enable_solr_indexing` is active and that you ran `python manage.py index -i work`
after the waffle switch was enabled. The import command disconnects signal-based indexing
to avoid duplicates, so you always need to run `index` manually after `ia_import`.
