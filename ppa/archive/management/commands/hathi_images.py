"""
**hathi_images** is a custom manage command for downloading both full-size
and thumbnail page images for a list of HathiTrust volumes.
"""
import argparse
from collections import Counter
from collections.abc import Iterable
import requests
from pathlib import Path
from time import sleep
from typing import Self

import progressbar
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import pluralize
from corppa.utils.path_utils import encode_htid, get_vol_dir

from ppa.archive.models import DigitizedWork
from ppa.archive.templatetags.ppa_tags import page_image_url


class DownloadStats:
    ACTION_TYPES = {"fetch", "skip"}
    def __init__(self):
        # Stats for full size images
        self.full = Counter()
        # Stats for thumbnail images
        self.thumbnail = Counter()

    def _log_action(self, image_type: str, action: str) -> None:
        if action not in self.ACTION_TYPES:
            raise ValueError(f"Unknown action type '{action}'")
        if image_type == "full":
            self.full[action] += 1
        elif image_type == "thumbnail":
            self.thumbnail[action] += 1
        else:
            raise ValueError(f"Unknown image type '{image_type}'")
    
    def log_download(self, image_type: str) -> None:
        self._log_action(image_type, "fetch")

    def log_skip(self, image_type: str) -> None:
        self._log_action(image_type, "skip")

    def update(self, other: Self) -> None:
        self.full.update(other.full)
        self.thumbnail.update(other.thumbnail)

    def get_report(self) -> str:
        return (
            f"Fetched {self.full['fetch']} images & "
            f"{self.thumbnail['fetch']} thumbnails; "
            f"Skipped {self.full['skip']} images & "
            f"{self.thumbnail['skip']} thumbnails"
        )


class Command(BaseCommand):
    """
    Download HathiTrust page image data via image server

    Note: Excerpts cannot be specified individually, only by source (collectively)
    """
    help = __doc__
    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    # Argument parsing
    def add_arguments(self, parser):
        """
        Configure additional CLI arguments
        """
        parser.add_argument(
            "output_dir",
            type=Path,
            help="Top-level output directory"
        )
        parser.add_argument(
            "--htids",
            nargs="+",
            help="Optional list of HathiTrust ids (by default, downloads images for all public HathiTrust volumes)",
        )
        parser.add_argument(
            "--crawl-delay",
            type=int,
            help="Delay to be applied between each download in seconds. Default: 1",
            default=1,
        )
        parser.add_argument(
            "--image-width",
            type=int,
            help="Width for full-size images in pixels. Default: 800",
            default=800,
        )
        parser.add_argument(
            "--thumbnail-width",
            type=int,
            help="Width for thumbnail images in pixels. Must be at most 250 pixels. Default: 250",
            default=250,
        )
        parser.add_argument(
            "--progress",
            action=argparse.BooleanOptionalAction,
            help="Display progress bars to track download progress",
            default=True,
        )
   
    def download_image(self, page_url: str, out_file: Path) -> bool:
        response = requests.get(page_url)
        success = False
        if response.status_code == requests.codes.ok:
            with out_file.open(mode="wb") as writer:
                writer.write(response.content)
            success = True
        else:
            if self.verbosity > self.v_normal:
                self.stdout(f"Warning: Failed to fetch image {out_file.name}")
        # Apply crawl delay after request
        sleep(self.crawl_delay)
        return success


    def download_volume_images(self, vol_id:str, page_range: Iterable) -> DownloadStats:
        # Determine output volume & thumbnail directories (create as needed)
        vol_dir = self.output_dir / get_vol_dir(vol_id)
        vol_dir.mkdir(parents=True, exist_ok=True)
        thumbnail_dir = vol_dir / "thumbnails"
        thumbnail_dir.mkdir(exist_ok=True)
            
        # Get filename-friendly version of htid
        clean_htid = encode_htid(vol_id)
            
        # Setup volume-level progress bar
        volume_progress = None
        if self.show_progress:
            volume_progress = progressbar.ProgressBar(
                line_offset=1, redirect_stdout=True, max_value=len(page_range), max_error=False
            )
            volume_progress.start()

        # Fetch images
        stats = DownloadStats()
        for page_num in page_range:
            image_name = f"{clean_htid}.{page_num:08d}.jpg"

            # Fetch thumbnail if file does not exist
            page_thumbnail = thumbnail_dir / image_name
            if not page_thumbnail.is_file():
                thumbnail_url = page_image_url(vol_id, page_num, self.thumbnail_width)
                success = self.download_image(thumbnail_url, page_thumbnail)
                # TODO: Should we log something different if the download fails?
                stats.log_download("thumbnail")
            else:
                stats.log_skip("thumbnail")

            # Fetch "full" image if file does not exist
            page_image = vol_dir / image_name
            if not page_image.is_file():
                image_url = page_image_url(vol_id, page_num, self.full_width)
                success = self.download_image(image_url, page_image)
                stats.log_download("full")
            else:
                stats.log_skip("full")
                
            # Update volume-specific progress bar
            if volume_progress:
                volume_progress.increment()
        # Finish volume-specific progress bar
        if volume_progress:
            volume_progress.finish()
        return stats


    def handle(self, *args, **kwargs):
        self.output_dir = kwargs["output_dir"]
        self.crawl_delay = kwargs["crawl_delay"]
        self.full_width = kwargs["image_width"]
        self.thumbnail_width = kwargs["thumbnail_width"]
        self.verbosity = kwargs.get("verbosity", self.verbosity)
        self.show_progress = kwargs["progress"]

        # Validate input arguments
        if not self.output_dir.is_dir():
            raise CommandError(
                f"Output directory '{self.output_dir}' does not exist or is not a directory"
            )
        if self.thumbnail_width > 250:
            raise CommandError(f"Thumbnail width cannot be more than 250 pixels")

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

        self.stdout.write(
            f"Downloading images for {digworks.count()} record{pluralize(digworks)}"
        )

        # setup main progress bar
        overall_progress = None
        if self.show_progress:
            overall_progress = progressbar.ProgressBar(
                line_offset=0, redirect_stdout=True, max_value=digworks.count(), max_error=False
            )
            overall_progress.start()

        overall_stats = DownloadStats()
        for digwork in digworks:
            vol_id = digwork.source_id
            # Determine page range
            if digwork.item_type == DigitizedWork.FULL:
                page_range = range(1, digwork.page_count+1)
            else:
                page_range = digwork.page_span
            
            vol_stats = self.download_volume_images(vol_id, page_range)
            overall_stats.update(vol_stats)
            # Update overall progress bar
            if overall_progress:
                overall_progress.increment()
        if overall_progress:
            overall_progress.finish()
        self.stdout.write("\n\n")  # To avoid overwriting progress bars
        self.stdout.write(self.style.SUCCESS(overall_stats.get_report()))
