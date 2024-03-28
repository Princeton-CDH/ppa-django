from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.core.management import call_command

from ppa.archive.models import DigitizedWork
from ppa.archive.management.commands import adjust_excerpts


@pytest.mark.django_db
class TestAdjustExcerptsCommand:
    @patch("ppa.archive.models.DigitizedWork.index_items")
    def test_update_success(self, mock_index_items):
        source_id = "abc.13245089"
        pages_orig = "10-20"
        pages_digital = "12-22"
        work = DigitizedWork.objects.create(
            source_id=source_id,
            pages_orig=pages_orig,
            pages_digital=pages_digital,
            source=DigitizedWork.OTHER,
        )

        cmd = adjust_excerpts.Command()
        cmd.setup()  # initialize stats dict

        # test with sample info coming from csv
        update_info = {
            "source_id": source_id,
            "pages_orig": pages_orig,
            "new_pages_digital": "15-25",
        }
        cmd.update_excerpt(update_info)
        assert cmd.stats["updated"] == 1
        # inspect the newly-excerpted work; get a fresh copy from the db
        excerpt = DigitizedWork.objects.get(pk=work.pk)
        assert excerpt.pages_digital == update_info["new_pages_digital"]

        # check that log entry was created to document the change
        log = LogEntry.objects.get(object_id=excerpt.pk)
        assert log.action_flag == CHANGE
        assert log.change_message == "Updated pages_digital"
        assert log.user.username == "script"

    def test_not_found(self, capsys):
        cmd = adjust_excerpts.Command()
        cmd.setup()  # initialize stats dict

        # test with sample info, no corresponding db record
        update_info = {
            "source_id": "abcs.123",
            "pages_orig": "i-iii",
            "new_pages_digital": "15-25",
        }
        cmd.update_excerpt(update_info)
        assert cmd.stats["notfound"] == 1
        captured = capsys.readouterr()
        assert "No record found" in captured.out

    def test_error(self, capsys):
        source_id = "abc.13245089"
        pages_orig = "10-20"
        pages_digital = "12-22"
        DigitizedWork.objects.create(
            source_id=source_id,
            pages_orig=pages_orig,
            pages_digital=pages_digital,
            source=DigitizedWork.OTHER,
        )

        cmd = adjust_excerpts.Command()
        cmd.setup()
        # test with sample info coming from csv
        update_info = {
            "source_id": source_id,
            "pages_orig": pages_orig,
            "new_pages_digital": "BOGUS",
        }
        cmd.update_excerpt(update_info)
        assert cmd.stats["error"] == 1
        # check captured output
        captured = capsys.readouterr()
        assert f"Error saving {source_id}" in captured.err

    def test_unchanged(self):
        source_id = "abc.13245089"
        pages_orig = "10-20"
        pages_digital = "12-22"
        DigitizedWork.objects.create(
            source_id=source_id,
            pages_orig=pages_orig,
            pages_digital=pages_digital,
            source=DigitizedWork.OTHER,
        )
        cmd = adjust_excerpts.Command()
        cmd.setup()

        # test with sample info coming from csv
        update_info = {
            "source_id": source_id,
            "pages_orig": pages_orig,
            "new_pages_digital": pages_digital,
        }
        cmd.update_excerpt(update_info)
        assert cmd.stats["unchanged"] == 1

    @patch("ppa.archive.models.DigitizedWork.index_items")
    def test_call_commmand(self, mock_index_items, tmp_path):
        source_id = "abc.13245089"
        pages_orig = "10-20"
        pages_digital = "12-22"
        DigitizedWork.objects.create(
            source_id=source_id, pages_orig=pages_orig, pages_digital=pages_digital
        )
        stdout = StringIO()
        # create minimal valid CSV with all required fields
        csvfile = tmp_path / "excerpt_updates.csv"
        csvfile.write_text(
            "\n".join(
                [
                    "source_id,pages_orig,new_pages_digital",
                    f"{source_id},{pages_orig},25-30",
                ]
            )
        )
        call_command("adjust_excerpts", csvfile, stdout=stdout)
        output = stdout.getvalue()
        assert "Updated 1 record." in output
        assert "0 errors" in output
        assert "0 not found" in output
        assert "0 unchanged" in output
