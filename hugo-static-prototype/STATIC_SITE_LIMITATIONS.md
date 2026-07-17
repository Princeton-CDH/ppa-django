---
title: "Static Site Limitations Analysis"
layout: "single"
---

This document records what we discovered by building a Hugo static site
prototype of the Princeton Prosody Archive. It was written in response to a
code review question: *"Why do we need a database web app? Why can't we just
use a static site?"*

The short answer: a static site handles *browsing and discovery* adequately,
but breaks down on the core research affordances that define the archive.

---

## What the prototype demonstrates works

### 1. Metadata browsing

Hugo's [content adapters](https://gohugo.io/content-management/content-adapters/)
let us read `cookbook_works.json` (76 records) and `scifi_works.json` (14,974
records) at build time and generate one HTML page per work. This works well.
Each detail page renders title, author, subjects/genres, publication date, and
external links from the JSON.

### 2. Pre-built facet index pages

Hugo can generate one page per distinct facet value — `/subgenres/aliens/`,
`/subjects/cooking/`, `/years/2011/`. Each lists all works with that value.
This gives coarse "browse by subject" navigation at zero runtime cost.

### 3. Client-side title/author filter

A small JavaScript function (`assets/js/search.js`) hides list items whose
`data-title` or `data-author` attributes don't contain the query string.
This works for small collections without a server.

### 4. Multi-collection architecture

The `_content.gotmpl` adapter pattern maps cleanly onto the Django adapter
YAML concept: each collection is a directory with its own data source and
field set.

---

## Where the static approach breaks down

### Limitation 1 — Full-text search across page content

**The fundamental problem.** The Django PPA stores digitized page content in
Solr. A researcher can search for a phrase like *"iambic pentameter"* and find
every page across thousands of volumes where that phrase appears, ranked by
relevance.

A static site has no equivalent mechanism:

- Page content would have to be embedded in HTML at build time. A single
  HathiTrust volume can have 400–600 pages of OCR text. At archival scale
  (hundreds of thousands of pages) this means gigabytes of HTML that no CDN
  or browser can handle gracefully.
- Even if the text were embedded, there is no way to rank results by relevance,
  apply stemming, boost title matches over body matches, or use phrase
  proximity. JavaScript string matching is not a search engine.

**Hugo content adapters** can generate pages from structured JSON, but they
cannot index free-form OCR text across a corpus and return ranked search
results. That is definitionally a server-side operation.

### Limitation 2 — Search-within a single work

Related to Limitation 1. After finding a work, researchers use the
"search within this work" feature to find a specific passage inside a
multi-hundred-page volume. The `single.html` layout in this prototype
renders a disabled placeholder for this feature. It cannot be implemented
without a query backend.

### Limitation 3 — Faceted search with query-scoped counts

The Django+Solr version computes facet counts dynamically. When a user
searches for *"robot"* and the results are 823 works, the subgenre facet
shows counts only for those 823 — e.g. "Aliens (214)", "Time Travel (88)".

Hugo can only pre-build *total* counts per facet value. It cannot:
- Count only the documents matching the current query
- Combine multiple active filters (subgenre AND date range AND keyword)
- Update counts after a keyword search changes the working set

The `filters.html` partial in this prototype notes this limitation inline.

**Scale of the combinatorial explosion:** With 14,974 works, ~20 subgenres,
~50 year values, and keyword search, the number of distinct filter states
is astronomically large. Pre-building a page for each state is not feasible.

### Limitation 4 — Date range slider

The PPA search form has a date range histogram and slider (implemented as a
Stimulus controller + RxJS). The user drags handles to narrow by publication
year. This requires:

1. A query engine that can filter `pub_date >= X AND pub_date <= Y`
2. Counts per year bucket *for the current result set* (not global counts)

A static site can link to pre-built year pages (`/years/2011/`), but cannot
implement a continuous slider that intersects with keyword search and other
active facets.

### Limitation 5 — Pagination at scale

`list.html` notes: Hugo supports `.Paginator`, but each page in a paginated,
faceted list is a distinct URL. With 14,974 works at 20 per page, that is
748 pages *before* factoring in filter combinations. Pre-building every
combination is not tractable.

In testing, rendering all 14,974 scifi works into a single HTML list (as the
prototype does) produces a ~3 MB page that causes visible scroll jank in the
browser. A real deployment would need either server-side pagination or a
JavaScript virtual-scroll component loading from a pre-built JSON index —
which is essentially rebuilding a search backend in the browser.

### Limitation 6 — Collection administration

The Django PPA has a Wagtail CMS and Django admin. Curators can:
- Add, edit, or suppress individual works without rebuilding the entire site
- Associate works with collections
- Edit editorial essays that link to archive content
- Manage adapter configuration per collection

A static site requires a full rebuild for any content change. At 14,974
records, `hugo build` takes several seconds. At HathiTrust scale (millions
of pages), a full rebuild is impractical. Incremental builds help but do not
eliminate the constraint.

### Limitation 7 — Access control and suppression

Some digitized works must be suppressed after ingestion (rights clearance,
quality issues). The Django application can suppress a work instantly by
flipping a database flag. A static site requires a rebuild and redeployment.

### Limitation 8 — Personalization and user accounts

The PPA roadmap includes saved searches and reading lists. These require
server-side session state. Static sites can use localStorage as a rough
substitute, but data is local to one browser and cannot be backed up,
shared, or recovered.

---

## Build-time cost summary

| Dataset | Records | `hugo build` time (local, M2) | Output size |
|---------|---------|-------------------------------|-------------|
| Cookbooks | 76 | ~1 s | ~500 KB HTML |
| Science fiction | 14,974 | ~8 s | ~42 MB HTML |
| Estimated HathiTrust scale | ~17 M pages | hours | impractical |

Build time grows roughly linearly with record count. At HathiTrust scale,
even if page content were excluded, a full rebuild would take many hours.

---

## Conclusion

A static site generator is an appropriate choice for **content-first sites**:
documentation, editorial essays, project blogs, small curated collections
with stable metadata and no full-text search requirement.

The PPA is a **corpus research tool**. Its defining features are:

1. Full-text search across hundreds of thousands of digitized pages
2. Ranked, relevance-scored results with stemming and phrase proximity
3. Faceted filtering with query-scoped counts
4. Search within individual works
5. Date range filtering with histogram visualization
6. Administrative workflows for curation and rights management

None of these can be satisfactorily implemented in a purely static site.
The prototype demonstrates points 1–4 of this list directly by showing
where its implementation either breaks down or requires caveats that amount
to *"this is a stub for a feature that needs a server"*.

The Django + Solr architecture is not over-engineering for a web app that
could have been a static site. It is the minimum viable architecture for the
research affordances the archive is designed to provide.
