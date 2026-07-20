# Data Sources Reference

This document describes each data source supported (or planned) in ppa-reuse: what
files get fetched, in what format, and how the parsing works. Use it when you want to
understand what the import pipeline actually does with a given source, or when you are
planning to add a new adapter for one of these providers.

---

## Summary table

| Source | Format | Page boundaries | Auth required | OCR quality | Status |
|---|---|---|---|---|---|
| Internet Archive | DjVu XML / hOCR / plain text | Yes (DjVu XML, hOCR); No (plain text) | None for public domain; S3 keys for restricted | Variable (machine OCR, 1800s–1900s texts) | Implemented |
| HathiTrust | Per-page `.txt` files in ZIP + METS XML | Yes | Institutional access + rsync credentials | Variable (machine OCR) | Implemented |
| Gale / ECCO | MARC/CSV metadata + optional local OCR JSON | Yes (via local OCR JSON) | Gale API username | Variable | Implemented |
| EEBO-TCP / ECCO-TCP | TEI XML (P4 and P5) | Yes (`<pb>` elements) | None (Phase I and II freely available) | High (manually keyed) | Implemented |
| Project Gutenberg | UTF-8 plain text / HTML / EPUB | No (plain text) | None | N/A (typeset source) | Planned |

---

## Internet Archive

**Implementation:** `ppa/archive/internet_archive.py`

### Metadata

Metadata is fetched live at import time from the IA Metadata API:

```
GET https://archive.org/metadata/{identifier}
```

The response is a JSON object. The `metadata` key contains bibliographic fields; the
`files` key lists all files attached to the item. PPA extracts the following from
`metadata`:

| IA field | PPA field |
|---|---|
| `title` | `title` |
| `creator` | `author` |
| `date` | `pub_date` (first four-digit year extracted via regex) |
| `publisher` | `publisher` |
| `place_of_publication` | `pub_place` |
| `language` | `language` |
| `description` | `metadata.description` |
| `subject` | `metadata.subject` |

IA returns empty dict `{}` for identifiers that do not exist, which the client treats
as a 404.

### Full text

The client inspects the `files` list from the metadata response and selects the best
available text file using this priority order:

1. **DjVu XML** (`*_djvu.xml`) — preferred; structured per-page OCR
2. **hOCR HTML** (`*_hocr.html`) — fallback; per-page OCR in HTML
3. **Plain text** (`*.txt`) — last resort; no page structure

The selected file is downloaded from:

```
GET https://archive.org/download/{identifier}/{filename}
```

#### DjVu XML format

DjVu XML files are typically 1–8 MB. Structure:

```xml
<DjVuXML>
  <BODY>
    <PAGE number="1" width="..." height="...">
      <WORD coords="...">text</WORD>
      <WORD coords="...">text</WORD>
      ...
    </PAGE>
    <PAGE number="2" ...>
      ...
    </PAGE>
  </BODY>
</DjVuXML>
```

The parser iterates `<PAGE>` elements and joins `<WORD>` text nodes with spaces. The
`number` attribute becomes the `page_id` (prefixed `p`) and the page label. Coordinate
attributes on `<WORD>` elements are not used.

#### hOCR HTML format

hOCR is an HTML microformat for OCR output. Pages are `<div class="ocr_page">` elements.
Page numbers are extracted from the `title` attribute of the page div:

```html
<div class="ocr_page" title="image ...; ppageno 3; ...">
  ...OCR text...
</div>
```

The `ppageno` value from `title` is used as the page number. The parser is a simple
state-machine (`html.parser.HTMLParser`) that tracks nesting depth to correctly close
each page and collect its text content.

#### Plain text format

Plain text files have no page boundary information. The entire file content is treated
as a single page with `page_id = "p1"` and `label = None`. This is a known limitation
documented in the code.

### Authentication

No authentication is required for public-domain metadata or content. For items with
restricted access, set `IA_ACCESS_KEY` and `IA_SECRET_KEY` in Django settings. The
client sends these as an `Authorization: LOW access:secret` header on download
requests.

The optional `TECHNICAL_CONTACT` setting adds a `From:` header to all requests, which
IA recommends for bulk access.

### IA identifier format

IA identifiers are alphanumeric strings with underscores, hyphens, and dots, up to 80
characters. Examples: `scienceofenglish00laniuoft`, `gutenberg-1234`. They map
directly to `DigitizedWork.source_id`.

---

## HathiTrust

**Implementation:** `ppa/archive/hathi.py` (and related files)

### Metadata

HathiTrust metadata comes from two sources:

- **MARC records** — bibliographic data in MARC21 format, parsed with `pymarc`
- **HathiTrust Bibliographic API** — REST API at `http://catalog.hathitrust.org/api`
  returning JSON with titles, publication dates, and item-level data

The bib API is queried by identifier type and value:

```
GET http://catalog.hathitrust.org/api/volumes/brief/{id_type}/{id_value}.json
GET http://catalog.hathitrust.org/api/volumes/full/{id_type}/{id_value}.json
```

A 200 response with no `records` key in the JSON body is treated as not-found.

### Full text

HathiTrust provides full text through a pairtree directory structure (using the
`pairtree` Python library). Each volume is stored as:

```
{pairtree_root}/{pairtree_path}/{volume_id}/
    {page_number}.txt      # one file per page
    *.mets.xml             # METS structural metadata
```

Pages are individual `.txt` files, one per page, bundled in a ZIP archive. The METS
XML (`*.mets.xml`) provides the structural map — page sequence, page labels, and
reading order. PPA uses `neuxml` for METS XML parsing.

Access to the pairtree data requires:
- Institutional HathiTrust membership
- rsync credentials to download the pairtree data locally

### Authentication

HathiTrust requires institutional access for full-text content. There is no public
download API for page text; content must be rsync'd to local storage. The rsync command
management (`hathi_rsync.py`) handles this sync.

---

## Gale / ECCO

**Implementation:** `ppa/archive/gale.py`

### Metadata

Gale metadata is imported from MARC records or CSV exports. The Gale API
(`https://api.gale.com/api`) is used to fetch item-level data at import time.

The API client (`GaleAPI`) is a singleton that automatically retrieves and refreshes an
API key using the configured `GALE_API_USERNAME`. Keys expire after 30 minutes; the
client handles refresh transparently.

Gale item identifiers begin with `CW` or `CB` followed by a numeric string
(e.g. `CW0128905397`).

### Full text

Gale does not provide a public API for full-text page content. Instead, PPA supports
**local OCR JSON files** when `GALE_LOCAL_OCR` is set in Django settings.

Local OCR files are organized in stub directories:

```
{GALE_LOCAL_OCR}/{stub_dir}/{item_id}.json
```

The stub directory is derived from every third character of the item ID (e.g.
`CW0128905397` → stub `193`). This convention matches the layout established by
`ppa-nlp`.

The JSON file is a dict keyed by 4-digit page number strings (e.g. `"0004"`), with
page text as values.

If `GALE_LOCAL_OCR` is not set, `gale_import` will raise `ImproperlyConfigured` when
attempting to index page content.

### Authentication

Gale requires a `GALE_API_USERNAME` in Django settings. The API is not publicly
accessible; institutional credentials are needed.

---

## EEBO-TCP / ECCO-TCP

**Implementation:** `ppa/archive/eebo_tcp.py`

### Format

EEBO-TCP (Early English Books Online — Text Creation Partnership) and ECCO-TCP
(Eighteenth Century Collections Online TCP) provide texts as **TEI XML**, in either
P4 (no namespaces) or P5 (`http://www.tei-c.org/ns/1.0`) encoding. The code handles
both transparently using `neuxml` for XML mapping.

The parser supports both namespace variants by checking tag names against both plain
and namespaced versions at parse time.

### Metadata

Metadata is embedded in the TEI header (`<teiHeader>`). There is no separate metadata
API call.

Volume identifiers in the import spreadsheet use the format `A25820.0001.001`; the TCP
record uses only the first portion (`A25820`), extracted by `short_id()`.

### Structure

Page boundaries are marked with `<pb>` (page break) elements. The `eebo_tcp.py` module
provides XML object classes for:

- `MixedText` — handles mixed content (text + inline elements), including detection of
  text nested inside `<NOTE>` and `<BIBL>` elements
- `TeiXmlObject` — base class with namespace registration for P5

Notable features:
- `<gap>` elements (representing illegible or missing text) are tracked separately
- Notes (`<NOTE>`) and bibliographic citations (`<BIBL>`) can be distinguished from
  body text for filtering purposes
- Lines (`<l>`) are the primary text unit for verse texts

### Authentication

EEBO-TCP Phase I and Phase II texts are freely available. No authentication is required.
ECCO-TCP texts are similarly open.

---

## Project Gutenberg (planned)

**Implementation:** not yet implemented

Project Gutenberg is the suggested next adapter for new contributors. It exercises
plain-text ingestion with no page boundaries — the simplest possible full-text case —
and requires no authentication.

### Metadata

The Gutenberg catalog is distributed as an RDF catalog:

```
https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv
https://www.gutenberg.org/cache/epub/feeds/rdf-files.tar.bz2
```

The CSV catalog contains `Text#`, `Type`, `Issued`, `Title`, `Language`, `Authors`,
`Subjects`, `LoCC`, `Bookshelves` columns and is suitable for batch import without
parsing RDF.

Individual item metadata is also available as RDF:

```
https://www.gutenberg.org/ebooks/{id}.rdf
```

### Full text

Plain text files are available at:

```
https://www.gutenberg.org/files/{id}/{id}-0.txt        # UTF-8
https://www.gutenberg.org/ebooks/{id}.txt.utf-8        # canonical URL
```

HTML and EPUB formats are also available but add parsing complexity without benefit for
full-text search. The plain text format is the recommended starting point.

**Limitation:** Gutenberg plain text files have no page boundaries. Like the IA plain
text fallback, the entire file would be indexed as a single page. This is acceptable
for search but means page-level navigation is not possible.

Some texts include a Project Gutenberg header and footer (license boilerplate) that
should be stripped before indexing. A marker line `*** START OF THE PROJECT GUTENBERG
EBOOK` / `*** END OF THE PROJECT GUTENBERG EBOOK` delimits the actual content.

### Authentication

None required. Gutenberg requests that automated access use reasonable rate limiting
and identify the client via `User-Agent`.

### Suggested implementation path

1. Create `examples/adapters/gutenberg/adapter.yaml` with a `field_map` covering
   `title`, `author`, `pub_date`, and `metadata.gutenberg_id`
2. Add a `gutenberg_import` management command (modelled on `ia_import`) that reads
   identifiers from a CSV and fetches metadata from the catalog CSV + full text from
   the canonical text URL
3. Add a `enable_gutenberg` waffle switch
4. Strip PG header/footer boilerplate before indexing page content
5. Since there are no page boundaries, yield a single page dict per item (same pattern
   as `_pages_from_plaintext` in `internet_archive.py`)
