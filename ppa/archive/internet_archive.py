"""
Internet Archive API client for PPA import.

Requires the ``internetarchive`` Python package (``pip install internetarchive``).

Settings
--------
No mandatory settings — the IA API is open for public metadata.  Optional:

* **TECHNICAL_CONTACT** — email address included as ``From`` request header.
* **IA_ACCESS_KEY** / **IA_SECRET_KEY** — S3-like credentials needed only when
  downloading restricted items.  Most public-domain texts do not need them.

Identifier format
-----------------
Internet Archive identifiers are alphanumeric strings with underscores and
hyphens, e.g. ``gutenberg-1234`` or ``TheProdigalGuestOfHonour1905``.  They are
used directly as :attr:`~ppa.archive.models.DigitizedWork.source_id`.
"""

import logging

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from ppa import __version__ as ppa_version

logger = logging.getLogger(__name__)

#: Base URL for the IA Metadata API
METADATA_API = "https://archive.org/metadata"

#: Base URL for IA item detail pages (used as source_url)
DETAILS_URL = "https://archive.org/details"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class IAError(Exception):
    """Base exception for Internet Archive API errors."""


class IAItemNotFound(IAError):
    """Requested IA item does not exist."""


class IANoFullText(IAError):
    """Item exists but has no machine-readable full-text file."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_valid_ia_id(identifier):
    """Return True if *identifier* looks like a plausible IA identifier.

    IA identifiers consist of letters, digits, underscores, hyphens, and dots.
    They must be between 1 and 80 characters long.
    """
    if not identifier or len(identifier) > 80:
        return False
    return all(c.isalnum() or c in "-_." for c in identifier)


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------


class InternetArchiveAPI:
    """Minimal Internet Archive client for PPA.

    Uses the public Metadata API (no authentication required for metadata)
    and the S3-like download API for page text.

    The client is intentionally *not* a singleton — unlike the Gale API it
    does not manage expiring API keys, so there is no benefit to sharing state.
    """

    def __init__(self):
        self.session = requests.Session()
        ua = "ppa-django/%s (%s)" % (
            ppa_version,
            self.session.headers["User-Agent"],
        )
        headers = {"User-Agent": ua}
        tech_contact = getattr(settings, "TECHNICAL_CONTACT", None)
        if tech_contact:
            headers["From"] = tech_contact
        self.session.headers.update(headers)

        # Optional S3-style credentials for restricted downloads
        access = getattr(settings, "IA_ACCESS_KEY", None)
        secret = getattr(settings, "IA_SECRET_KEY", None)
        if access and secret:
            self.session.headers["authorization"] = "LOW %s:%s" % (access, secret)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_metadata(self, identifier):
        """Return the raw metadata dict for *identifier* from the IA Metadata API.

        Raises :exc:`IAItemNotFound` if the item does not exist or the API
        returns a non-200 response.
        """
        url = "%s/%s" % (METADATA_API, identifier)
        logger.debug("GET %s", url)
        resp = self.session.get(url, timeout=30)
        if resp.status_code == requests.codes.not_found:
            raise IAItemNotFound(identifier)
        resp.raise_for_status()
        data = resp.json()
        # IA returns {} (empty dict) for identifiers that don't exist
        if not data:
            raise IAItemNotFound(identifier)
        return data

    # ------------------------------------------------------------------
    # Full-text / page content
    # ------------------------------------------------------------------

    def get_fulltext_filename(self, files):
        """Given the ``files`` list from IA metadata, return the filename of
        the best available plain-text file, or ``None`` if none exists.

        Preference order:
        1. ``_djvu.xml``  — structured DjVu XML with per-page text
        2. ``_hocr.html`` — hOCR HTML with per-page text
        3. ``_full_text.txt`` / ``*.txt`` — plain text (no page boundaries)
        """
        djvu = hocr = plain = None
        for f in files:
            name = f.get("name", "")
            if name.endswith("_djvu.xml") and djvu is None:
                djvu = name
            elif name.endswith("_hocr.html") and hocr is None:
                hocr = name
            elif name.endswith(".txt") and plain is None:
                plain = name
        return djvu or hocr or plain

    def get_item_pages(self, identifier, ia_metadata=None):
        """Return a generator of page-content dicts for *identifier*.

        Each dict has the keys expected by
        :meth:`~ppa.archive.models.Page.page_index_data`:

        * ``page_id``  — string page identifier
        * ``content``  — OCR text for the page (may be ``None`` / empty)
        * ``label``    — human-readable page label (may be ``None``)

        When *ia_metadata* is provided the Metadata API call is skipped.

        Raises :exc:`IAItemNotFound` if the item does not exist.
        Raises :exc:`IANoFullText` if no usable text file is found.
        """
        if ia_metadata is None:
            ia_metadata = self.get_metadata(identifier)

        files = ia_metadata.get("files", [])
        text_filename = self.get_fulltext_filename(files)
        if text_filename is None:
            raise IANoFullText(
                "No plain-text or DjVu XML file found for %s" % identifier
            )

        if text_filename.endswith("_djvu.xml"):
            yield from self._pages_from_djvu(identifier, text_filename)
        elif text_filename.endswith("_hocr.html"):
            yield from self._pages_from_hocr(identifier, text_filename)
        else:
            yield from self._pages_from_plaintext(identifier, text_filename)

    def _download_text(self, identifier, filename):
        """Download and return the raw text of *filename* for *identifier*."""
        url = "https://archive.org/download/%s/%s" % (identifier, filename)
        logger.debug("Downloading %s", url)
        resp = self.session.get(url, timeout=120)
        resp.raise_for_status()
        return resp.text

    def _pages_from_djvu(self, identifier, filename):
        """Parse a DjVu XML file and yield per-page dicts.

        DjVu XML structure (simplified)::

            <DjVuXML>
              <BODY>
                <PAGE number="1" ...>
                  <WORD ...>text</WORD> ...
                </PAGE>
                ...
              </BODY>
            </DjVuXML>
        """
        try:
            # stdlib xml is fine here — we control the source (IA's own OCR)
            import xml.etree.ElementTree as ET  # noqa: PLC0415

            raw = self._download_text(identifier, filename)
            root = ET.fromstring(raw)
        except Exception as exc:
            logger.warning("Failed to parse DjVu XML for %s: %s", identifier, exc)
            return

        for page_el in root.iter("PAGE"):
            page_num = page_el.get("number", "")
            words = " ".join(w.text or "" for w in page_el.iter("WORD") if w.text)
            yield {
                "page_id": "p%s" % page_num,
                "content": words.strip() or None,
                "label": page_num or None,
            }

    def _pages_from_hocr(self, identifier, filename):
        """Parse an hOCR HTML file and yield per-page dicts.

        hOCR pages are ``<div class="ocr_page">`` elements.
        """
        try:
            # Use html.parser — no lxml dependency required
            from html.parser import HTMLParser  # noqa: PLC0415

            raw = self._download_text(identifier, filename)

            # Simple state-machine parser to extract page text from hOCR
            class HocrParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.pages = []
                    self._current = None
                    self._depth = 0

                def handle_starttag(self, tag, attrs):
                    attrs_dict = dict(attrs)
                    cls = attrs_dict.get("class", "")
                    if "ocr_page" in cls:
                        title = attrs_dict.get("title", "")
                        page_num = ""
                        for part in title.split(";"):
                            part = part.strip()
                            if part.startswith("ppageno"):
                                page_num = part.split()[-1]
                        self._current = {"page_id": "p%s" % page_num, "label": page_num or None, "_buf": []}
                        self._depth = 1
                    elif self._current is not None:
                        self._depth += 1

                def handle_endtag(self, tag):
                    if self._current is not None:
                        self._depth -= 1
                        if self._depth == 0:
                            content = " ".join(self._current["_buf"]).strip()
                            self._current["content"] = content or None
                            del self._current["_buf"]
                            self.pages.append(self._current)
                            self._current = None

                def handle_data(self, data):
                    if self._current is not None:
                        text = data.strip()
                        if text:
                            self._current["_buf"].append(text)

            parser = HocrParser()
            parser.feed(raw)
            yield from parser.pages

        except Exception as exc:
            logger.warning("Failed to parse hOCR for %s: %s", identifier, exc)
            return

    def _pages_from_plaintext(self, identifier, filename):
        """Yield a single pseudo-page from a plain-text file.

        Plain-text files have no page boundaries, so the entire text is
        treated as a single page.  This is documented as a limitation.
        """
        try:
            content = self._download_text(identifier, filename)
        except Exception as exc:
            logger.warning("Failed to download text for %s: %s", identifier, exc)
            return
        yield {
            "page_id": "p1",
            "content": content.strip() or None,
            "label": None,
        }

    # ------------------------------------------------------------------
    # Convenience: normalised bibliographic fields
    # ------------------------------------------------------------------

    @staticmethod
    def parse_metadata(ia_metadata):
        """Extract a dict of normalised PPA-compatible fields from raw IA metadata.

        Returns a dict with keys: ``title``, ``author``, ``pub_date``,
        ``publisher``, ``pub_place``, ``description``, ``language``.
        All values may be ``None`` or empty string.
        """
        meta = ia_metadata.get("metadata", {})

        # title: prefer full_title, fall back to title
        title = meta.get("title") or ""
        if isinstance(title, list):
            title = title[0]

        # creator / author
        creator = meta.get("creator") or ""
        if isinstance(creator, list):
            creator = "; ".join(creator)

        # publication date — IA stores as string; extract first 4-digit year via regex
        date_raw = meta.get("date") or ""
        if isinstance(date_raw, list):
            date_raw = date_raw[0] if date_raw else ""
        pub_date = None
        import re as _re  # noqa: PLC0415 — localised to avoid top-level dependency
        _year_match = _re.search(r"\b(\d{4})\b", str(date_raw))
        if _year_match:
            pub_date = int(_year_match.group(1))

        # publisher
        publisher = meta.get("publisher") or ""
        if isinstance(publisher, list):
            publisher = "; ".join(publisher)

        # place of publication
        pub_place = meta.get("publisher") or meta.get("place_of_publication") or ""
        if isinstance(pub_place, list):
            pub_place = pub_place[0]
        # IA often conflates publisher with place; prefer an explicit field
        explicit_place = meta.get("place_of_publication") or ""
        if isinstance(explicit_place, list):
            explicit_place = explicit_place[0]
        if explicit_place:
            pub_place = explicit_place

        # language
        language = meta.get("language") or ""
        if isinstance(language, list):
            language = language[0]

        # description
        description = meta.get("description") or ""
        if isinstance(description, list):
            description = description[0]

        return {
            "title": str(title).strip(),
            "author": str(creator).strip(),
            "pub_date": pub_date,
            "publisher": str(publisher).strip(),
            "pub_place": str(pub_place).strip(),
            "language": str(language).strip(),
            "description": str(description).strip(),
        }
