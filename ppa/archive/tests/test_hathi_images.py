from io import StringIO
from unittest.mock import Mock, call, patch

import pytest
import requests
import signal

from ppa.archive.templatetags.ppa_tags import page_image_url
from ppa.archive.management.commands import hathi_images


class TestDownloadStats:
    def check_stats(
        self,
        stats: hathi_images.DownloadStats,
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
        stats = hathi_images.DownloadStats()
        self.check_stats(stats, 0, 0, 0, 0)

    def test_log_action(self):
        stats = hathi_images.DownloadStats()
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

    @patch.object(hathi_images.DownloadStats, "_log_action")
    def test_log_download(self, mock_log_action):
        stats = hathi_images.DownloadStats()
        stats.log_download("image_type")
        mock_log_action.assert_called_once_with("image_type", "fetch")

    @patch.object(hathi_images.DownloadStats, "_log_action")
    def test_log_skip(self, mock_log_action):
        stats = hathi_images.DownloadStats()
        stats.log_skip("image_type")
        mock_log_action.assert_called_once_with("image_type", "skip")

    @patch.object(hathi_images.DownloadStats, "_log_action")
    def test_log_error(self, mock_log_action):
        stats = hathi_images.DownloadStats()
        stats.log_skip("image_type")
        mock_log_action.assert_called_once_with("image_type", "error")

    def test_update(self):
        stats_a = hathi_images.DownloadStats()
        stats_b = hathi_images.DownloadStats()
        stats_b.full["fetch"] = 5
        stats_b.full["skip"] = 1
        stats_b.thumbnail["fetch"] = 3
        stats_b.thumbnail["skip"] = 2
        self.check_stats(stats_b, 5, 1, 3, 2 )

        stats_a.update(stats_b)
        self.check_stats(stats_a, 5, 1, 3, 2)
        self.check_stats(stats_b, 5, 1, 3, 2 )

        stats_a.update(stats_b)
        self.check_stats(stats_a, 10, 2, 6, 4)
        self.check_stats(stats_b, 5, 1, 3, 2 )

    def test_report(self):
        stats = hathi_images.DownloadStats()
        assert stats.get_report() == "No actions taken"

        # Only actions that have occurred are reported 
        stats.full["fetch"] = 5
        report = "Fetched: 5 images & 0 thumbnails"
        assert stats.get_report() == report

        stats.thumbnail["skip"] = 3
        report += "\nSkipped: 0 images & 3 thumbnails"
        assert stats.get_report() == report

        stats.full["error"] = 1
        stats.thumbnail["error"] = 2
        report += "\nMissed: 1 images & 2 thumbnails"
        assert stats.get_report() == report


class TestHathiImagesCommand:
    @patch("signal.signal")
    def test_interrupt_handler(self, mock_signal):
        stdout = StringIO()
        cmd = hathi_images.Command(stdout=stdout)
        
        cmd.interrupt_handler(signal.SIGINT, "frame")
        mock_signal.assert_called_once_with(signal.SIGINT, signal.SIG_DFL)
        assert cmd.interrupted
        assert stdout.getvalue() == (
            "Command will exit once this volume's image download is complete.\n"
            "Ctrl-C / Interrupt to quit immediately\n"
        )

    def test_download_image(self, tmp_path):
        cmd = hathi_images.Command()
        cmd.session = Mock()
        
        # Not ok status
        cmd.session.get.return_value = Mock(status_code=503)
        result = cmd.download_image("page_url", "out_file")
        cmd.session.get.assert_called_once_with("page_url")
        assert result is False

        # Ok status
        out_file = tmp_path / "test.jpg"
        cmd.session.reset_mock()
        cmd.session.get.return_value = Mock(status_code=200, content=b"image content")
        result = cmd.download_image("page_url", out_file)
        cmd.session.get.assert_called_once_with("page_url")
        assert result is True
        assert out_file.read_text() == "image content"
