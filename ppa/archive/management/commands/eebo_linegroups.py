import pathlib
import csv

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from eulxml import xmlmap

from ppa.archive import eebo_tcp
from ppa.archive.models import DigitizedWork


class Command(BaseCommand):
    """Report on linegroups in EEBO-TCP content"""

    help = __doc__
    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    # def add_arguments(self, parser):
    #     parser.add_argument(
    #         "csv", type=str, help="CSV file with EEBO-TCP items to import."
    #     )

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

        with open("tcp-linegroups.csv", "w", encoding="utf-8-sig") as csvfile:
            csvwriter = csv.DictWriter(
                csvfile,
                fieldnames=[
                    "source_id",
                    "source_title",
                    # "source_excerpt",
                    # "excerpt_digital_pages",
                    "start_page_index",
                    "end_page_index",
                    "start_page_n",
                    "end_page_n",
                    "text",
                    "source_note",
                    "language",
                ],
            )
            csvwriter.writeheader()

            # eebo-tcp works
            for work in digworks:
                tcp_text = eebo_tcp.load_tcp_text(work.source_id)
                csvwriter.writerows(self.linegroups_for_text(work, tcp_text))

            # ecco-tcp works
            for work in ecco_digworks:
                tcp_text = xmlmap.load_xmlobject_from_file(
                    self.ecco_tcp_path / f"{work.source_id}.xml", eebo_tcp.Text
                )
                csvwriter.writerows(self.linegroups_for_text(work, tcp_text))

    def linegroups_for_text(self, work, tcp_text):
        # given a DigitizedWork and a TCP text, return a list of
        # dictionaries with line groups found
        linegroups = []
        for lg in tcp_text.line_groups:
            # TODO: PB REF != page number necessarily...
            # get based on index?
            # TODO: can we do better on page numbers?

            # TODO: skip if it's all gap / foreign language / no text

            # if work is an excerpt, only include line groups in range
            if work.item_type != DigitizedWork.FULL:
                # if line groups start page is not in page span, skip
                if int(lg.start_page.index) not in work.page_span:
                    continue

            # otherwise, add line group details to the CSV
            linegroups.append(
                {
                    "source_id": work.source_id,
                    "source_title": work.title,
                    # "source_excerpt": "N"
                    # if work.item_type == DigitizedWork.FULL
                    # else "Y",
                    # "excerpt_digital_pages": work.pages_digital,
                    "start_page_index": lg.start_page.index,
                    "end_page_index": lg.continue_page.index
                    if lg.continue_page
                    else None,
                    "start_page_n": lg.start_page.number,
                    "end_page_n": lg.continue_page.number if lg.continue_page else None,
                    # "text": str(lg),
                    "text": lg.text,
                    "source_note": lg.source,
                    "language": lg.language,
                }
            )
        return linegroups
