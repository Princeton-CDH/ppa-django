import requests
from pathlib import Path
from time import sleep

import progressbar
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import pluralize
from corppa.utils.path_utils import encode_htid, get_vol_dir

from ppa.archive.models import DigitizedWork
from ppa.archive.templatetags.ppa_tags import page_image_url


class Command(BaseCommand):
    """
    Download HathiTrust page image data via image server

    Note: Excerpts cannot be specified individually, only by source (collectively)
    """
    help = __doc__
    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal
    #: crawl delay (in seconds)
    crawl_delay=1
    def add_arguments(self, parser):
        parser.add_argument(
            "out",
            type=Path,
            help="Top-level output directory")
        parser.add_argument(
            "--htids",
            nargs="*",
            help="Optional list of HathiTrust ids (by default, downloads images for all public HathiTrust volumes)",
        )
        parser.add_argument(
            "--progress",
            action="store_true",
            help="Display progress bars to track download progress",
            default=True,
        )
    
    def download_image(self, page_url: str, out_file: Path) -> None:
        response = requests.get(page_url)
        if response.status_code == requests.codes.ok:
            with out_file.open(mode="wb") as writer:
                writer.write(response.content)
        # Apply crawl delay after request
        sleep(self.crawl_delay)


    def handle(self, *args, **kwargs):
        self.verbosity = kwargs.get("verbosity", self.v_normal)
        self.options = kwargs

        # validate output directory
        if not kwargs["out"]:
            raise CommandError("An output directory must be specified")
        output_dir = kwargs["out"]
        if not output_dir.is_dir():
            raise CommandError(
                f"Output directory '{output_dir}' does not exist or is not a directory"
            )

        # use ids specified via command line when present
        htids = kwargs.get("htids", [])

        # by default, download images for all non-suppressed hathi source ids
        digworks = DigitizedWork.objects.filter(
            status=DigitizedWork.PUBLIC, source=DigitizedWork.HATHI
        )

        # if htids are specified via parameter, use them to filter
        # the queryset, to ensure we only sync records that are
        # in the database and not suppressed
        if htids:
            digworks = digworks.filter(source_id__in=htids)

        # bail out if there's nothing to do
        # (e.g., explicit htids only and none valid)
        if not digworks.exists():
            self.stdout.write("No records to download; stopping")
            return

        # setup main progress bar
        overall_progress = None
        if self.options["progress"]:
            overall_progress = progressbar.ProgressBar(
                redirect_stdout=True, max_value=digworks.count(), max_error=False
            )
            overall_progress.start()

        self.stdout.write(
            f"Downloading images for {digworks.count()} record{pluralize(digworks)}"
        )

        for digwork in digworks:
            vol_id = digwork.source_id
            
            # Determine output volume & thumbnail directories (create as needed)
            vol_dir = output_dir / get_vol_dir(vol_id)
            vol_dir.mkdir(parents=True, exist_ok=True)
            thumbnail_dir = vol_dir / "thumbnails"
            thumbnail_dir.mkdir(exist_ok=True)
            
            # Get filename-friendly version of htid
            clean_htid = encode_htid(vol_id)
            
            # Determine page range
            if digwork.item_type == DigitizedWork.FULL:
                page_range = range(1, digwork.page_count+1)
            else:
                page_range = digwork.page_span
            
            # Setup volume-level progress bar
            volume_progress = None
            if self.options["progress"]:
                volume_progress = progressbar.ProgressBar(
                    redirect_stdout=True, max_value=len(page_range), max_error=False
                )
                volume_progress.start()

            # Fetch images
            stats = {
                "image": {"fetch": 0, "skip": 0},
                "thumbnail": {"fetch": 0, "skip": 0}
            }
            for page_num in page_range:
                image_name = f"{clean_htid}.{page_num:08d}.jpg"

                # Fetch thumbnail if file does not exist
                page_thumbnail = thumbnail_dir / image_name
                if not page_thumbnail.is_file():
                    thumbnail_url = page_image_url(vol_id, page_num, 250)
                    self.download_image(thumbnail_url, page_thumbnail)
                    stats["thumbnail"]["fetch"] += 1
                else:
                    stats["thumbnail"]["skip"] += 1

                # Fetch "full" image if file does not exist
                page_image = vol_dir / image_name
                if not page_image.is_file():
                    image_url = page_image_url(vol_id, page_num, 800)
                    #self.download_image(image_url, page_image)
                    stats["image"]["fetch"] += 1
                else:
                    stats["image"]["skip"] += 1
                
                # Update volume-specific progress bar
                if volume_progress:
                    volume_progress.increment()
            # Finish volume-specific progress bar
            if volume_progress:
                volume_progress.finish()
            self.stdout.write(
                f"{vol_id}: Fetched {stats['image']['fetch']} images & "
                f"{stats['thumbnail']['fetch']} thumbnails; "
                f"Skipped {stats['image']['skip']} images & "
                f"{stats['thumbnail']['skip']} thumbnails"
            )
            # Update overall progress bar
            if overall_progress:
                overall_progress.increment()
        if overall_progress:
            overall_progress.finish()
