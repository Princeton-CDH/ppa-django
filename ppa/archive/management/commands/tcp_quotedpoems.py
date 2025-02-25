import pathlib
import csv
import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import pluralize
from eulxml import xmlmap
import progressbar

from ppa.archive import eebo_tcp, gale
from ppa.archive.models import DigitizedWork, Page


class Command(BaseCommand):
    """Generate a spreadsheet of quoted poetry in EEBO-TCP and ECCO-TCP content"""

    help = __doc__
    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    def add_arguments(self, parser):
        # add source group to limit to ecco or eebo
        # argparse built in prefixing; lower case args but display proper case
        source_arg_group = parser.add_argument_group("Source", "Limit to one source")
        source_arg_group.add_argument(
            "--ecco",
            help="ECCO-TCP",
            dest="source",
            action="store_const",
            const="ecco",
        )
        source_arg_group.add_argument(
            "--eebo",
            help="EEBO-TCP",
            dest="source",
            action="store_const",
            const="eebo",
        )

    def handle(self, *args, **kwargs):
        self.verbosity = kwargs.get("verbosity", self.v_normal)
        source = kwargs.get("source")

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

        if source == "eebo" or source is None:
            # find all EEBO works in the database
            digworks = DigitizedWork.objects.filter(
                status=DigitizedWork.PUBLIC, source=DigitizedWork.EEBO
            )
            self.stdout.write(f"Found {digworks.count()} EEBO-TCP works")

        ecco_digworks = []
        if source == "ecco" or source is None:
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
                    "ppa_excerpt_text",
                    "start",
                    "end",
                    "notes",
                ],
            )
            csvwriter.writeheader()
            count_qpoems = 0

            # eebo-tcp works
            if source == "eebo" or source is None:
                progbar = progressbar.ProgressBar(
                    prefix="EEBO-TCP: ",
                    redirect_stdout=True,
                    max_value=digworks.count(),
                )
                count = 0
                progbar.update(count)
                # FIXME: there's a slowdown between here; related to solr client init? (why?)
                for work in digworks:
                    tcp_text = eebo_tcp.load_tcp_text(work.source_id)
                    quoted_poems = self.get_quoted_poems(work, tcp_text)
                    csvwriter.writerows(quoted_poems)
                    count_qpoems += len(quoted_poems)
                    count += 1
                    progbar.update(count)

                self.stdout.write(
                    f"\nCompleted EEBO-TCP, found {count_qpoems:,} poem excerpts"
                )

            # ecco-tcp works
            if source == "ecco" or source is None:
                progbar = progressbar.ProgressBar(
                    prefix="ECCO-TCP: ",
                    redirect_stdout=True,
                    max_value=ecco_digworks.count(),
                )
                count = 0  # reset count for progress bar for ecco-tcp subset
                progbar.update(count)
                for work in ecco_digworks:
                    tcp_text = xmlmap.load_xmlobject_from_file(
                        self.ecco_tcp_path / f"{work.source_id}.xml", eebo_tcp.Text
                    )
                    quoted_poems = self.get_quoted_poems(work, tcp_text)
                    csvwriter.writerows(quoted_poems)
                    count_qpoems += len(quoted_poems)
                    count += 1
                    progbar.update(count)

        self.stdout.write(f"\nFound {count_qpoems:,} poem excerpts total")

    def get_quoted_poems(self, work, tcp_text):
        # given a DigitizedWork and a TCP text, return a list of
        # dictionaries with information about quoted poems
        poems = []
        work_index_id = work.index_id()
        # load page content so we can confirm page ids and
        # get span start/end index within page text content
        if work.source == DigitizedWork.EEBO:
            # for eebo, use the page index data used for indexing solr,
            # which is generated from local xml
            work_page_contents = Page.page_index_data(work)
            # get the first page of data from the generator
            page_data = next(work_page_contents)
        elif work.source == DigitizedWork.GALE:
            # for ecco, load local ocr file
            work_page_contents = gale.get_local_ocr(work.source_id)
            page_data = None

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

                # increase the page number when on a chunk of text
                # that follows a page break
                page = page_index + i

                # page id must match what we use for ppa indexing & text export
                # we use work index id (= volume id or volume+start page for excerpt)
                # in combination with page id; for eebo-tcp, this is 1-based page index
                # for ECCO, we use page number from ecco api

                if work.source == DigitizedWork.EEBO:
                    # eebo page ids are numbered based on work index id
                    # and page id from the xml
                    # NOTE: have manually confirmed ids match for EEBO-TCP works
                    page_id = f"{work_index_id}.{page}"

                    # since we find quoted poems sequentially, we can consume
                    # pages from the page index data generator until we find the
                    # page with the current page id
                    while page_data["id"] != page_id:
                        page_data = next(work_page_contents)

                elif work.source == DigitizedWork.GALE:
                    # gale/ecco page ids have leading zeroes
                    gale_page = f"{page:04d}"
                    page_id = f"{work_index_id}.{gale_page}"
                    # get text content from local ocr by page number
                    page_data = {"content": work_page_contents[gale_page]}

                # if excerpt cannot be found on page text, start/end will be None
                start_index, end_index = get_excerpt_span(
                    text_chunk, page_data["content"]
                )

                notes = []
                if qpoem.source:
                    notes.append(f"Source: {qpoem.source}")
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
                ppa_excerpt_text = ""
                excerpt_length = len(text_chunk)
                if start_index and end_index:
                    ppa_excerpt_text = page_data["content"][start_index:end_index]
                elif start_index:
                    ppa_excerpt_text = page_data["content"][
                        start_index : start_index + excerpt_length
                    ]
                elif end_index:
                    ppa_excerpt_text = page_data["content"][
                        end_index - excerpt_length : end_index
                    ]

                poems.append(
                    {
                        "page_id": page_id,
                        "source_id": work.source_id,
                        "source_title": work.title,
                        "text": text_chunk,
                        "ppa_excerpt_text": ppa_excerpt_text,
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
    # ecco-tcp includes long S that ecco-ocr renders as f
    # for simplicity, replace in both texts before comparing
    # (since this is a single-character replacement, it doesn't impact index)
    _excerpt = excerpt.replace("ſ", "f")
    _page_text = page_text.replace("ſ", "f")

    try:
        # best case scenario: the entire text matches exactly
        start_index = _page_text.index(_excerpt)
        end_index = start_index + len(excerpt)
    except ValueError:
        # if re_note_marks.search(page_text):
        # TODO: flip this! remove the note marks from the page text instead?

        # if excerpt includes two whitepace characters in a row,
        # we may be missing a footnote marker
        # if re.search("\s\s", excerpt):
        #     # print("double whitespace, looking for not marks")
        #     excerpt_pattern = re.sub(
        #         "(\s)(\s)", f"\1{note_marks_charset}?\2", excerpt
        #     )
        #     match = re.search(excerpt_pattern, page_text)
        #     if match:
        #         start_index, end_index = match.span()

        if not start_index:
            lines = _excerpt.split("\n")
            # if we have more than one line, try by first/last?
            if len(lines) > 1:
                # print("attempting to find start/end based on first/last line")
                # print(lines[0].strip())
                start_index, _ = get_excerpt_span(lines[0].strip(), page_text)
                # print(f"first line: found start={start} end={_}")
                _, end_index = get_excerpt_span(lines[-1].strip(), page_text)
                # print(lines[-1].strip())
                # print(f"last line: found start={_} end={end}")
                # if start or end:
                # print(f"found something start={start} end={end}")

    return (start_index, end_index)
