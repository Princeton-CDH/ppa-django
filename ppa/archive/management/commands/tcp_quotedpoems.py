import pathlib
import csv
import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import pluralize
from eulxml import xmlmap

from ppa.archive import eebo_tcp
from ppa.archive.models import DigitizedWork, Page


class Command(BaseCommand):
    """Generate a spreadsheet of quoted poetry in EEBO-TCP and ECCO-TCP content"""

    help = __doc__
    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    def handle(self, *args, **kwargs):
        self.verbosity = kwargs.get("verbosity", self.v_normal)

        # make sure eebo data path is configured in django settings
        if not getattr(settings, "EEBO_DATA", None):
            raise CommandError(
                "Path for EEBO_DATA must be configured in Django settings"
            )
        self.eebo_data_path = pathlib.Path(settings.EEBO_DATA)
        if not self.eebo_data_path.exists():
            raise CommandError(
                f"EEBO_DATA directory {self.eebo_data_path} does not exist"
            )

        # find all EEBO works in the database
        digworks = DigitizedWork.objects.filter(
            status=DigitizedWork.PUBLIC, source=DigitizedWork.EEBO
        )
        self.stdout.write(f"Found {digworks.count()} EEBO-TCP works")

        ecco_digworks = []
        if hasattr(settings, "ECCO_TCP_DATA"):
            self.ecco_tcp_path = pathlib.Path(settings.ECCO_TCP_DATA)
            ecco_tcp_ids = [p.stem for p in self.ecco_tcp_path.glob("*.xml")]
            self.stdout.write(f"Found {len(ecco_tcp_ids)} ECCO-TCP xml files")

            ecco_digworks = DigitizedWork.objects.filter(source_id__in=ecco_tcp_ids)

        with open("tcp_quotedpoems.csv", "w", encoding="utf-8-sig") as csvfile:
            csvwriter = csv.DictWriter(
                csvfile,
                fieldnames=[
                    "page_id",
                    "source_id",
                    "source_title",
                    "text",
                    "start",
                    "end",
                    "notes",
                ],
            )
            csvwriter.writeheader()

            # eebo-tcp works
            for work in digworks:
                tcp_text = eebo_tcp.load_tcp_text(work.source_id)
                csvwriter.writerows(self.get_quoted_poems(work, tcp_text))

            # ecco-tcp works
            for work in ecco_digworks:
                tcp_text = xmlmap.load_xmlobject_from_file(
                    self.ecco_tcp_path / f"{work.source_id}.xml", eebo_tcp.Text
                )
                csvwriter.writerows(self.get_quoted_poems(work, tcp_text))

    def get_quoted_poems(self, work, tcp_text):
        # given a DigitizedWork and a TCP text, return a list of
        # dictionaries with information about quoted poems
        poems = []
        work_index_id = work.index_id()
        # for page span index we need access to text as indexed in solr
        # for convine
        work_page_contents = Page.page_index_data(work)
        page_data = next(work_page_contents)

        for qpoem in tcp_text.quoted_poems:
            page_index = int(qpoem.start_page.index)

            # if this is in an excerpt, check if it is in range
            if work.item_type != DigitizedWork.FULL:
                # if quoted poem start page is not in page span, skip
                if page_index not in work.page_span:
                    continue

            # quoted poems may wrap across page boundaries
            # output run row per paged chunk of poem text
            poem_chunks = list(qpoem.text_by_page())
            for i, text_chunk in enumerate(poem_chunks):
                text_chunk = text_chunk.strip()  # remove whitespace on the edges

                # in some cases a chunk may have no text content
                # but it still indicates a page break
                if not text_chunk:
                    continue

                page = page_index + i

                # page id must match what we use for ppa indexing & text export
                # we use work index id (= volume id or volume+start page for excerpt)
                # in combination with page id; for eebo-tcp, this is 1-based page index
                # for ECCO, we use page number from ecco api

                if work.source == DigitizedWork.EEBO:
                    # eebo page ids are numbered as is
                    # NOTE: have manually confirmed ids match for EEBO-TCP works
                    page_id = f"{work_index_id}.{page}"
                elif work.source == DigitizedWork.GALE:
                    # gale/ecco page ids have leading zeroes
                    page_id = f"{work_index_id}.{page:04d}"
                    # TODO: figure out how/if TCP pages match up with Gale/ECCO ...
                    # maybe counting front-matter differently?

                # since we find quoted poems sequentially, we can consume
                # pages from the page index data generator until we find the
                # page with the current page id
                while page_data["id"] != page_id:
                    page_data = next(work_page_contents)

                # print(f"page {page} page id {page_id};  page data {page_data['id']}")

                # if excerpt cannot be found on page text, start/end will be None
                start_index, end_index = get_excerpt_span(
                    text_chunk, page_data["content"]
                )

                notes = []
                # add a note if we wrapped pages and previous chunk had content
                if i != 0 and poem_chunks[i - 1]:
                    notes.append("Continued quotation from previous page")
                # in at least one case, we have any linegroups with language
                # information; include that in the notes
                languages = [lg.language for lg in qpoem.line_groups if lg.language]
                if languages:
                    notes.append(
                        f"Language{pluralize(languages)}: {','.join(languages)}"
                    )
                # some documents have marginal notes with a citation
                for note in qpoem.notes:
                    notes.append(f"{note.label}: {note}")

                # add quoted poem details to list of dictionaries for output
                poems.append(
                    {
                        "page_id": page_id,
                        "source_id": work.source_id,
                        "source_title": work.title,
                        "text": text_chunk,
                        "start": start_index,
                        "end": end_index,
                        "notes": "\n".join(notes),
                    }
                )
        return poems


# regex to check for note markers
note_marks_charset = f"[{''.join(eebo_tcp.Page.note_marks)}]"
re_note_marks = re.compile(note_marks_charset)


def get_excerpt_span(excerpt, page_text):
    start_index = end_index = None
    try:
        # best case scenario: the entire text matches exactly
        start_index = page_text.index(excerpt)
        end_index = start_index + len(excerpt)
    except ValueError:
        if re_note_marks.search(page_text):
            # if excerpt includes two whitepace characters in a row,
            # we may be missing a footnote marker
            if re.search("\s\s", excerpt):
                excerpt_pattern = re.sub(
                    "(\s)(\s)", f"\1{note_marks_charset}?\2", excerpt
                )
                match = re.search(excerpt_pattern, page_text)
                if match:
                    start_index, end_index = match.span()

        if not start_index:
            lines = excerpt.split("\n")
            # if we have more than one line, try by first/last?
            if len(lines) > 1:
                print("attempting to find start/end based on first/last line")
                start, _ = get_excerpt_span(lines[0], page_text)
                _, end = get_excerpt_span(lines[-1], page_text)

    return (start_index, end_index)
