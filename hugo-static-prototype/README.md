# Hugo Static Site Prototype

A static site prototype of the Princeton Prosody Archive, built with
[Hugo](https://gohugo.io/) v0.160+ to stress-test the limits of a
static-site approach for a digital humanities archive.

## Purpose

This prototype was built in response to a reviewer question:
*"Why do we need a database web app? Why can't we just use a static site?"*

It demonstrates what a static generator can do well and — more importantly —
where it breaks down for the core research affordances of a corpus archive.
See [STATIC_SITE_LIMITATIONS.md](STATIC_SITE_LIMITATIONS.md) for the full analysis.

## What it covers

| Feature | Status |
|---------|--------|
| Metadata pages for 76 cookbooks | ✅ works |
| Metadata pages for 14,974 science fiction works | ✅ works |
| Pre-built per-facet index pages | ✅ works (via taxonomy) |
| Client-side title/author filter | ✅ works (JavaScript) |
| Multi-collection architecture via content adapters | ✅ works |
| Full-text search across page content | ❌ not possible |
| Search within a single work | ❌ not possible |
| Faceted filtering with query-scoped counts | ❌ not possible |
| Combined multi-facet filtering | ❌ not possible |
| Date range slider with histogram | ❌ not possible |
| Relevance-ranked results | ❌ not possible |
| Instant content suppression / admin workflows | ❌ not possible |

## Data

The prototype uses two real datasets from the adapter system:

- **cookbooks** — 76 historical American cookbooks from Michigan State
  University Library Digital & Multimedia Center (`assets/data/cookbook_works.json`)
- **scifi** — 14,974 science fiction works from Goodreads
  (`assets/data/scifi_works.json`)

These are the same datasets used by the Django adapter examples in
`examples/adapters/cookbook/` and `examples/adapters/scifi/`.

## Quick start

Requires [Hugo extended](https://gohugo.io/installation/) v0.112 or later
(content adapters require v0.112+).

```bash
cd hugo-static-prototype
hugo server          # dev server at http://localhost:1313
hugo build           # static output to public/
```

The build generates ~15,000 pages in about 2 seconds on an M-series Mac.
The scifi list page renders all 14,974 works into a single ~3 MB HTML file —
this is intentional and documents the pagination limitation.

## How the content adapters work

Hugo
[content adapters](https://gohugo.io/content-management/content-adapters/)
(`_content.gotmpl`) are Go templates that run at build time and call
`$.AddPage` to create pages from data. Each adapter directory has one:

```
content/adapters/
├── cookbook/
│   ├── _content.gotmpl    ← reads cookbook_works.json, creates 76 pages
│   └── _index.md          ← section front matter
└── scifi/
    ├── _content.gotmpl    ← reads scifi_works.json, creates 14,974 pages
    └── _index.md
```

The `_content.gotmpl` files read from `assets/data/*.json` via
`resources.Get`, unmarshal the JSON, and iterate over records calling
`$.AddPage` for each one. This is the Hugo equivalent of the Django adapter
YAML + import script pattern.

## Correspondence with Django adapter system

| Hugo concept | Django equivalent |
|---|---|
| `content/adapters/<name>/` | `examples/adapters/<name>/` |
| `_content.gotmpl` | `adapter.yaml` + import script |
| `assets/data/<name>_works.json` | `DigitizedWork.metadata` JSONField |
| `layouts/partials/filters.html` | Solr facets in `ArchiveSearchView` |
| `assets/js/search.js` | Solr full-text query |

## File structure

```
hugo-static-prototype/
├── hugo.toml                          # site configuration
├── README.md                          # this file
├── assets/
│   ├── css/main.css                   # site styles
│   ├── data/
│   │   ├── cookbook_works.json        # 76 cookbook records
│   │   └── scifi_works.json           # 14,974 scifi records
│   └── js/search.js                   # client-side title/author filter
├── STATIC_SITE_LIMITATIONS.md         # limitations analysis
├── content/
│   └── adapters/
│       ├── cookbook/
│       │   ├── _content.gotmpl        # content adapter
│       │   └── _index.md
│       └── scifi/
│           ├── _content.gotmpl        # content adapter
│           └── _index.md
└── layouts/
    ├── index.html                     # home page
    ├── _default/
    │   ├── baseof.html                # base template
    │   ├── list.html                  # collection browse page
    │   └── single.html                # work detail page
    └── partials/
        ├── head.html
        ├── header.html
        ├── footer.html
        ├── work-card.html             # card in list view
        └── filters.html               # sidebar with limitation notes
```

## Read the limitations analysis

The full analysis lives at `STATIC_SITE_LIMITATIONS.md` (root of this directory).
It covers 8 specific limitations with explanations of why each one requires a
server-side query engine rather than a static site.
