"""
**hathi_images** is a custom manage command for downloading both full-size
and thumbnail page images for a list of HathiTrust volumes.
"""
import argparse
from collections import Counter
from collections.abc import Iterable
import logging
import requests
from pathlib import Path
import signal
from time import sleep
from typing import Self

from tqdm import tqdm
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import pluralize
from corppa.utils.path_utils import encode_htid, get_vol_dir

from ppa.archive.models import DigitizedWork
from ppa.archive.templatetags.ppa_tags import page_image_url

logger = logging.getLogger(__name__)


class DownloadStats:
    # Support actions
    ACTION_TYPES = {"fetch", "skip", "error"}
    # Associated strings used for reporting
    ACTION_STRS = {
        "fetch": "Fetched",
        "skip": "Skipped",
        "error": "Missed",
    }

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

    def log_error(self, image_type: str) -> None:
        self._log_action(image_type, "error")

    def update(self, other: Self) -> None:
        self.full.update(other.full)
        self.thumbnail.update(other.thumbnail)

    def get_report(self) -> str:
        report = ""
        for action in ["fetch", "skip", "error"]:
            if action == "error":
                # Only report errors when an error is present
                if not self.full[action] and not self.thumbnail[action]:
                    continue
            action_str = self.ACTION_STRS[action]
            if report:
                report += "\n"
            report += f"{action_str}: {self.full[action]} images & {self.thumbnail[action]} thumbnails"
        return report


class Command(BaseCommand):
    """
    Download HathiTrust page image data via image server

    Note: Excerpts cannot be specified individually, only by source (collectively)
    """
    help = __doc__

    # Interrupt flag to exit gracefully (i.e. between volumes) when a signal is caught
    interrupted = False

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
  
    def interrupt_handler(self, signum, frame):
        """
        For handling of SIGINT, as possible. For the first SIGINT, a flag is set
        so that the command will exit after the current volume's image download
        is complete. Additionally, the default signal handler is restored so a
        second SIGINT will cause the command to immediately exit.
        """
        if signum == signal.SIGINT:
            # Restore default signal handler
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            # Set interrupt flag
            self.interrupted = True
            self.stdout.write(self.style.WARNING(
                "Command will exit once this volume's image download is "
                "complete.\n Ctrl-C / Interrupt to quit immediately"
                )
            )

    def download_image(self, page_url: str, out_file: Path) -> bool:
        response = requests.get(page_url)
        # log response time
        logger.debug(f"Response time: {response.elapsed.total_seconds()}")
        self.stdout.write(str(response.headers))
        success = False
        if response.status_code == requests.codes.ok:
            with out_file.open(mode="wb") as writer:
                writer.write(response.content)
            success = True
            # For checking throttling rates
            # TODO: Consider removing once crawl delays are determined
            choke_str = "x-choke info:"
            for choke_sfx in ['allowed', 'credit', 'delta', 'max', 'rate']:
                header = f"x-choke-{choke_sfx}"
                if header in response.headers:
                    choke_str += f"\n  {header}: {response.headers[header]}"
            logger.debug(choke_str)
        elif response.status_code == 503:
            logger.debug("WARNING: Received 503 status code. Throttling may have occurred")
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
            
        # Fetch images
        stats = DownloadStats()
        for page_num in page_range:
            image_name = f"{clean_htid}.{page_num:08d}.jpg"

            for image_type in ["full", "thumbnail"]:
                image_dir = vol_dir if image_type == "full" else thumbnail_dir
                image = image_dir / image_name
                image_width = getattr(self, f"{image_type}_width")

                # Fetch image does not exist
                if not image.is_file():
                    image_url = page_image_url(vol_id, page_num, image_width)
                    success = self.download_image(image_url, image)
                    if success:
                        stats.log_download(image_type)
                    else:
                        stats.log_error(image_type)
                        logger.debug(f"Failed to download {image_type} image {image_name}")
                else:
                    stats.log_skip(image_type)

            # Update progress bar
            if self.show_progress:
                self.progress_bar.update()
        return stats


    def handle(self, *args, **kwargs):
        self.output_dir = kwargs["output_dir"]
        self.crawl_delay = kwargs["crawl_delay"]
        self.full_width = kwargs["image_width"]
        self.thumbnail_width = kwargs["thumbnail_width"]
        self.show_progress = kwargs["progress"]

        # Validate input arguments
        if not self.output_dir.is_dir():
            raise CommandError(
                f"Output directory '{self.output_dir}' does not exist or is not a directory"
            )
        if self.thumbnail_width > 250:
            raise CommandError("Thumbnail width cannot be more than 250 pixels")

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
        
        # Bind handler for interrupt signal
        signal.signal(signal.SIGINT, self.interrupt_handler)

        n_vols = digworks.count()
        self.stdout.write(
            f"Downloading images for {n_vols} record{pluralize(digworks)}",
        )

        # Initialize progress bar
        if self.show_progress:
            self.progress_bar = tqdm()
       
        overall_stats = DownloadStats()
        for i, digwork in enumerate(digworks):
            vol_id = digwork.source_id
            # Determine page range
            if digwork.item_type == DigitizedWork.FULL:
                page_range = range(1, digwork.page_count+1)
            else:
                page_range = digwork.page_span
           
            # Update progress bar
            if self.show_progress:
                self.progress_bar.reset(total=len(page_range))
                self.progress_bar.set_description(
                    f"{vol_id} ({i+1}/{n_vols})"
                )

            vol_stats = self.download_volume_images(vol_id, page_range)
            overall_stats.update(vol_stats)
            # Update overall progress bar
            # Check if we need to exit early
            if self.interrupted:
                break
        # Close progres bar
        if self.show_progress:
            self.progress_bar.close()
        if self.interrupted:
            self.stdout.write(self.style.WARNING(f"Exited early with {i} volumes completed."))
        self.stdout.write(self.style.SUCCESS(overall_stats.get_report()))
