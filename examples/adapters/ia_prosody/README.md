# ia_prosody — Internet Archive Prosody Adapter

A PPA adapter for historical English-language texts on prosody, versification,
and the study of poetic metre, sourced from the Internet Archive (archive.org).

## Dataset

10 verified works spanning 1801–1910, all public domain with machine-readable
DjVu XML OCR text.

| Identifier | Title | Author | Date |
|---|---|---|---|
| `scienceofenglish00laniuoft` | The science of English verse | Lanier, Sidney | 1880 |
| `orthometrytreati00brewrich` | Orthometry: a treatise on the art of versification | Brewer, Robert Frederick | 1893 |
| `elementsofenglis00ruskrich` | Elements of English prosody | Ruskin, John | 1880 |
| `historyofenglish01gues` | A history of English rhythms (vol. 1) | Guest, Edwin | 1838 |
| `handbookofmodern00mayorich` | A handbook of modern English metre | Mayor, Joseph B. | 1903 |
| `elementsofenglis00briguoft` | The elements of English versification | Bright, James Wilson | 1910 |
| `blankverse00symoiala` | Blank verse | Symonds, John Addington | 1895 |
| `chaptersonengli00stofgoog` | Chapters on English printing, prosody, and pronunciation | van Dam & Stoffel | 1902 |
| `inquiryintoprinc00mitfiala` | An inquiry into the principles of harmony in language | Mitford, William | 1804 |
| `elementsofenglis00roeruoft` | The elements of English metre, both in prose and verse | Roe, Richard | 1801 |

These are real, live Internet Archive items. Each has been verified to have:
- A `_djvu.xml` file (structured per-page OCR text, 1–8 MB)
- A `_djvu.txt` plain-text fallback
- English-language content (`lang: eng`)

All items match the LCSH subject heading `"English language -- Versification"` and
are directly relevant to the Princeton Prosody Archive's core subject matter.

## How to import

Run the migration first, then import using the CSV:

```bash
python manage.py migrate
python manage.py ia_import -c examples/adapters/ia_prosody/ia_prosody_import.csv
```

Or import specific items by identifier:

```bash
python manage.py ia_import scienceofenglish00laniuoft orthometrytreati00brewrich
```

After import, reindex works and pages:

```bash
python manage.py index -i work
python manage.py index_pages
```

## Adapter fields

In addition to the standard `DigitizedWork` fields (title, author, pub_date, etc.),
this adapter tracks:

| Adapter field | Source | Description |
|---|---|---|
| `ia_prosody_subject` | `metadata.subject` | LCSH subject headings from IA metadata |
| `ia_prosody_description` | `metadata.description` | IA item description |
| `ia_prosody_ia_url` | `metadata.ia_url` | Direct link to item on archive.org |
| `ia_prosody_ia_id` | `metadata.ia_id` | Internet Archive identifier (same as source_id) |

## Why these texts?

The Princeton Prosody Archive focuses on historical documents about the *study*
of poetry — not poems themselves, but treatises on metre, rhythm, and versification.
These 10 items represent a core sample of that literature:

- **Lanier (1880)** and **Mayor (1903)** represent the "scientific" and
  "philological" camps in late-19th-century prosody debates.
- **Guest (1838)** is the foundational historical study that later prosodists
  either built on or argued against.
- **Ruskin (1880)** and **Bright (1910)** show the pedagogical strand —
  how prosody was taught.
- **Mitford (1804)** and **Roe (1801)** show the early-19th-century transition
  from classical (quantitative) to modern (accentual) frameworks.
- **van Dam & Stoffel (1902)** brings in the philological/historical dimension.

Together they demonstrate the full range of IA content that PPA can ingest:
from short pamphlets (Ruskin, ~1 MB) to large multi-volume works (Mitford, ~8 MB).

## Data provenance

All metadata is retrieved live from the Internet Archive Metadata API
(`https://archive.org/metadata/{identifier}`) at import time. The
`ia_prosody_works.json` file in this directory is a static snapshot for
reference and for use in the Hugo static-site prototype — it is not used by
the Django import command.
