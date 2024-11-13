from unittest.mock import call, patch

import pytest
import requests


from ppa.archive.templatetags.ppa_tags import page_image_url
from ppa.archive.management.commands.hathi_images import (
    DownloadStats,
)


class TestDownloadStats:
    def check_stats(
        self,
        stats: DownloadStats,
        full_fetch: int,
        full_skip: int,
        thumbnail_fetch: int,
        thumbnail_skip: int,
    ) -> None:
        """Helper function to check stats"""
        assert stats.full["fetch"] == full_fetch
        assert stats.full["skip"] == full_skip
        assert stats.thumbnail["fetch"] == thumbnail_fetch
        assert stats.thumbnail["skip"] == thumbnail_skip

    def test_init(self):
        stats = DownloadStats()
        self.check_stats(stats, 0, 0, 0, 0)

    def test_log_action(self):
        stats = DownloadStats()
        # unknown action type
        with pytest.raises(ValueError, match="Unknown action type 'bad_action'"):
            stats._log_action("image_type", "bad_action")

        # unknown image type
        with pytest.raises(ValueError, match="Unknown image type 'image_type'"):
            stats._log_action("image_type", "fetch")

        # Add one to each image type & action
        stats._log_action("full", "fetch")
        self.check_stats(stats, 1, 0, 0, 0)
        stats._log_action("full", "skip")
        self.check_stats(stats, 1, 1, 0, 0)
        stats._log_action("thumbnail", "fetch")
        self.check_stats(stats, 1, 1, 1, 0)
        stats._log_action("thumbnail", "skip")
        self.check_stats(stats, 1, 1, 1, 1)

        # Add another one to each image type & action
        stats._log_action("thumbnail", "skip")
        self.check_stats(stats, 1, 1, 1, 2)
        stats._log_action("full", "skip")
        self.check_stats(stats, 1, 2, 1, 2)
        stats._log_action("full", "fetch")
        self.check_stats(stats, 2, 2, 1, 2)
        stats._log_action("thumbnail", "fetch")
        self.check_stats(stats, 2, 2, 2, 2)

    @patch.object(DownloadStats, "_log_action")
    def test_log_download(self, mock_log_action):
        stats = DownloadStats()
        stats.log_download("image_type")
        mock_log_action.called_once_with("image_type", "fetch")

    @patch.object(DownloadStats, "_log_action")
    def test_log_skip(self, mock_log_action):
        stats = DownloadStats()
        stats.log_download("image_type")
        mock_log_action.called_once_with("image_type", "skip")

    def test_update(self):
        stats_a = DownloadStats()
        stats_b = DownloadStats()
        stats_b.full.update({"fetch": 5, "skip": 1})
        stats_b.thumbnail.update({"fetch": 3, "skip": 2})
        self.check_stats(stats_b, 5, 1, 3, 2 )

        stats_a.update(stats_b)
        self.check_stats(stats_a, 5, 1, 3, 2)
        self.check_stats(stats_b, 5, 1, 3, 2 )

        stats_a.update(stats_b)
        self.check_stats(stats_a, 10, 2, 6, 4)
        self.check_stats(stats_b, 5, 1, 3, 2 )

    def test_report(self):
        stats_a = DownloadStats()
        report_a = "Fetched 0 images & 0 thumbnails; Skipped 0 images & 0 thumbnails"
        assert stats_a.get_report() == report_a 

        stats_b = DownloadStats()
        stats_b.full.update({"fetch": 5, "skip": 1})
        stats_b.thumbnail.update({"fetch": 3, "skip": 2})
        report_b = "Fetched 5 images & 3 thumbnails; Skipped 1 images & 2 thumbnails"
        assert stats_b.get_report() == report_b
