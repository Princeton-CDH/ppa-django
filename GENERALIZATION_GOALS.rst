Generalizing ppa-django-reuse
=============================

Purpose
-------
This repository started as a fork of the Princeton Prosody Archive (PPA) web
application. The goal of `ppa-django-reuse` is to generalize that application into
a reusable, configurable platform that can host different kinds of archival
collections (e.g., musical notes, cookbooks, newspapers, images, or any other
domain-specific corpus).

Audience
--------
This document is for maintainers and contributors designing or implementing
changes to make the codebase adaptable to new archive types.

High-level goals
----------------
- Make data model and indexing pluggable so projects can reuse the UI and CMS
  while providing domain-specific models and Solr schema.
- Allow configuration-driven presentation (templates, fields, metadata labels)
  so the same codebase can render multiple domain UIs with minimal code change.
- Keep the Wagtail + Django admin experience familiar: allow editors to manage
  domain content while relying on the same publishing workflows.
- Provide example adapters for at least two non-PPA domains (suggested:
  Musical notation collection, Historical cookbooks).
- Provide clear developer and operator documentation to bootstrap new archive
  instances quickly.

Design principles
-----------------
- Backwards-compatible: existing PPA deployments should continue to work.
- Configuration-first: prefer configuration files and extension points over
  forking core application code.
- Small adapters: allow projects to ship small adapter modules for domain
  specifics (models, templates, solr mappings) instead of rewriting features.
- Explicit extension points: document where and how to plug in new behavior.
- Tests & examples: ship unit/integration tests and a minimal sample data set for
  each example adapter.

Scope
-----
This generalization effort focuses on:
- Content modeling: making the core content models and indexing layer extensible.
- Search/indexing: supporting pluggable Solr schemas and a local/no-op fallback
  for environments without Solr.
- Templates & assets: theming and template overrides so domain-specific
  templates can be supplied per deployment.
- Settings & deployment: clear configuration for database, Solr/Elastic, and
  static assets.

Out of scope (initial)
----------------------
- Replacing Solr with a different search engine (optional future work).
- Large-scale import tooling for new domains (we will provide example scripts).

Architecture / extension points
------------------------------
1. Settings and environment
   - The project already uses `ppa/settings/` split-settings. Encourage new
     deployments to provide `ppa/settings/local_settings.py` to override:
     - `SOLR_CONNECTIONS`, `DATABASES`, `HATHI_DATA` (or other domain data paths),
     - `WAGTAIL_SITE_NAME`, `MEDIA_ROOT`, `STATICFILES_DIRS`.
   - Add new config keys for `ARCHIVE_TYPE` and `ARCHIVE_ADAPTER` (module path).

2. Data model adapters
   - Provide a small adapter API that the core code imports if configured:
     - adapter module should expose:
       - models: optional Django models (or model mixins) to register additional fields
       - solr_schema: mapping from app model fields to solr dynamic fields
       - templates: mapping to template override directories
   - Default behavior: keep current PPA models; when `ARCHIVE_ADAPTER` is set,
     the adapter's models and mapping are used/merged.

3. Indexing & search
   - Parasolr-based client usage remains; provide:
     - a `FakeSolrClient` and defensive fallbacks (we added a Solr-safe fallback
       for the homepage).
     - adapter-provided Solr config (schema and configset) to be installed to
       the Solr server for each archive type.
   - Indexing commands should accept `--adapter` / `--schema` flags to build
     mappings per domain.

4. Templates & frontend
   - Theme mechanism: look up templates in a domain-specific directory before
     falling back to the default PPA templates. Adapters may include their own
     `templates/` and `static/` assets.
   - Use `APP_NAME` or `ARCHIVE_TYPE` in templates to toggle labels and UI text.

5. Admin/editor UX
   - Keep Wagtail page types generic and provide adapter mixins that add domain
     panels/fields to editorial pages.
   - Provide documentation for how to create new page types that rely on the
     adapter models.

Examples (minimal)
------------------
- Musical archive adapter:
  - Extra models: `Score`, `Movement`, `Instrument`, `NotationImage`.
  - Solr schema: fields for `tempo`, `key_signature`, `instrumentation`.
  - Templates: `templates/musical/` with overrides for search results and detail.

- Cookbook archive adapter:
  - Extra models: `Recipe`, `Ingredient`, `RecipeImage`, `PreparationStep`.
  - Solr schema: fields for `ingredients_exact`, `cooking_time`, `cuisine`.
  - Templates: `templates/cookbook/` with recipe-specific metadata blocks.

Migration and bootstrap plan
---------------------------
1. Document required settings and provide `ppa/settings/local_settings.py.sample`
   entries for new config keys (`ARCHIVE_TYPE`, `ARCHIVE_ADAPTER`).
2. Create a minimal adapter example for one domain (e.g., `examples/cookbook/`).
3. Provide an example Solr configset and an `index` management command that can
   load the adapter schema.
4. Add integration tests that start the dev server with `FakeSolrClient` to
   validate rendering without Solr.
5. Publish a short HOWTO in the repo root showing how to:
   - add an adapter,
   - configure settings,
   - run migrations,
   - build assets, and
   - deploy.

Acceptance criteria
-------------------
- New archive type can be added by dropping an adapter module and setting
  `ARCHIVE_ADAPTER` without modifying core code.
- Dev server renders homepage and detail pages with no Solr running (using
  `FakeSolrClient` or defensive fallbacks).
- Indexing commands can generate an adapter-specific Solr config and a
  compatible index for the new domain.
- A short example adapter and integration test exist in `examples/`.

Operational notes
-----------------
- For production search features, provide instructions to install the adapter's
  Solr configset into the target Solr server and to adjust `SOLR_CONNECTIONS`.
- Keep `local_settings.py` out of version control; use samples and environment
  variables for secrets and deployment-specific config.

Next steps
----------
1. Create an `examples/` directory with at least two adapter examples.
2. Implement small adapter API (module interface) and update README with
   quickstart.
3. Add tests exercising template overrides and Solr-fallback behavior.

Quickstart (development)
------------------------
To get a reproducible local dev environment with optional services:

1. Copy `ppa/settings/local_settings.py.sample` to `ppa/settings/local_settings.py` and set desired flags:

   - `ENABLE_SOLR_INDEXING = True` to enable Solr integration
   - `ENABLE_HATHI = True` to enable Hathi pairtree commands
   - `ENABLE_PUCAS = True` to enable CAS/PUCAS auth (requires additional setup)

2. Start optional dependencies with Docker Compose:

   ```bash
   docker compose -f docker/docker-compose.dev.yml up -d
   ```

3. Install Python dependencies (use virtualenv) and build assets:

   ```bash
   pip install -r requirements.txt  # includes optional corppa dependency (git+...)
   npm install
   npm run build
   python manage.py migrate
   python manage.py runserver
   ```

4. If Solr is enabled, visit `http://localhost:8983/solr` to check the admin UI.


Contact / ownership
-------------------
Maintainers of this repo should update this document as design decisions are
made. For discussion, open issues or PRs referencing this document.



Meeting notes and actionable decisions
------------------------------------
These items summarize mentor meeting notes and capture decisions, pain points,
and concrete recommendations that should be reflected in the generalization
work.

Quick decisions
++++++++++++++
- Start from a fork of the PPA Django codebase (`ppa-django`) and incrementally
  generalize templates, providers, and configuration.
- Provide tutorial-style documentation and a “quickstart” that uses Docker
  (recommended) to simplify developer setup and reduce environment pain points.
- Solr should remain the primary search engine for now; provide easy local
  orchestration (Docker Compose) and a `FakeSolrClient` fallback for demos and
  tutorial users who do not want to run Solr locally.

How to start (developer flow)
++++++++++++++++++++++++++++
1. Fork the repo.
2. Create and activate a Python virtualenv (or use the provided Docker Compose).
3. Build frontend assets (or run a webpack dev server) and run migrations.
4. Use an example adapter (see `examples/`) or create a minimal adapter for a
   test corpus (historical cookbooks suggested).
5. Iterate on adapter mappings (models, Solr schema, templates) and re-index.

Audience & sample data
++++++++++++++++++++++
- Audience: projects that want to build a searchable full-text archive from a
  variety of providers and formats (MARC, TEI/TCP, JSON, RDF, EPUB/text).
- Suggested sample datasets to prototype with: open EEBO-TCP / ECCO-TCP,
  Project Gutenberg excerpts, Internet Archive book metadata, or the MSU
  Feeding America dataset.
- Start with English datasets first; plan for multi-language (UI and indexing)
  support as a future enhancement.

Supported / target providers & formats
+++++++++++++++++++++++++++++++++++++
- HathiTrust (MARC + METS pairtree workflow): keep as a baseline adapter.
- Gale/Cengage (ECCO): MARC/CSV + optional local OCR import path.
- EEBO-TCP / ECCO-TCP: TEI / TCP adapter for open corpora (easy, consistent).
- Project Gutenberg: RDF + UTF-8 text/HTML/EPUB ingestion.
- Internet Archive: JSON metadata, ALTO/DJVU OCR; support REST-based retrieval.

What to generalize (summary)
++++++++++++++++++++++++++++
- Data model: loosen `DigitizedWork` constraints and support configurable
  fields or JSON blobs for sources without MARC or canonical page IDs.
- Provider layer: replace hard-coded Hathi/Gale/EEBO logic with pluggable
  adapters that fetch and normalize metadata and page text.
- Search setup: drive facets, range sliders, and Solr aliases from config rather
  than hard-coded field names.
- UI/branding: separate a neutral base theme and provide feature flags / themes
  so adopters can rebrand without editing core templates.
- CMS/editorial: ship optional Wagtail blocks/snippets as modules so deployments
  start minimal and opt into extras (contributors, DocRaptor).
- Configuration: reorganize settings so CAS, analytics, Solr configsets, and
  corppa/local-data paths are optional overlays with sample data packs.

Pain points and ops notes
++++++++++++++++++++++++
- Simplify or remove the `corppa` hard dependency for general use; where
  possible provide an adapter-compatible replacement or vendor minimal helper
  functionality inside an `examples/` adapter.
- Provide Docker Compose recipes that include a local PostgreSQL and Solr for
  new users (and optional sample datasets).
- Improve import documentation: describe MARC parsing workflow, TEI/TCP
  expectations, and how to map provider fields to Solr.

Tech choices & suggestions
++++++++++++++++++++++++++
- Use Docker/Docker Compose for simplified developer onboarding and reproducible
  local environments.
- For lightweight frontend interactivity consider Stimulus.js or Alpine.js (both
  are small and unobtrusive).
- Use django-waffle for runtime feature flags (togglable MARC support, themes,
  preview behaviors).
- Use `pyyaml` to allow simple YAML-driven configuration for content type
  definitions and adapter mappings, enabling `enable_custom_content_types` and
  `enable_configurable_imports`.
- Consider hosted Postgres (e.g., Supabase) as an optional quick production
  backend for prototypes.

Feature flags
+++++++++++++
Feature flags let adopters toggle support for optional features at runtime
without redeploying code. Use flags to gate:
- MARC-dependent ingest pipelines
- Advanced editorial modules
- Themed templates and branding
- Experimental indexing features

Conference / outreach (DH2026)
++++++++++++++++++++++++++++++
- Position the project as an open-source toolkit for building searchable
  full-text archives across multiple providers (HathiTrust, Gale, EEBO-TCP,
  Gutenberg, Internet Archive).
- Emphasize the decoupling of ingest, normalization, indexing, and Wagtail
  presentation. Showcase a live demo (spin up a mini Gutenberg dataset) and
  demonstrate adapter ease-of-use.
- Highlight lessons learned: metadata heterogeneity, rights/ethical handling,
  and sustainability (shared maintenance of ingest plugins).

Configuration-first content types
++++++++++++++++++++++++++++++++
With `enable_custom_content_types` and `enable_configurable_imports`, adapters
can define content types using YAML files (loaded via `pyyaml`) so projects
declare models, Solr field mappings, and templates in configuration instead of
Python code.

References and links
+++++++++++++++++++
- django-waffle: `https://github.com/django-waffle/django-waffle`
- Supabase (hosted Postgres): `https://supabase.com/`
- Example dataset (MSU Feeding America): `https://lib.msu.edu/feedingamericadata`

