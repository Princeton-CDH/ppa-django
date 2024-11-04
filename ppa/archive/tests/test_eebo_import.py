from unittest.mock import patch

import pytest
from django.core.management.base import CommandError
from django.test import override_settings

from ppa.archive.models import DigitizedWork
from ppa.archive.management.commands import eebo_import
from ppa.archive.tests.test_models import FIXTURES_PATH


@pytest.mark.django_db
class TestEEBOImportCommand:
    def test_load_csv(self, tmp_path):
        cmd = eebo_import.Command()
        # simulate successful load and parse of CSV with all required fields
        csvfile = tmp_path / "eebo_works.csv"
        # volume id is the only required filed
        csvfile.write_text(
            "\n".join(
                [
                    "Volume ID,Title",
                    "A12345,About Rhyme",
                ]
            )
        )
        data = cmd.load_csv(csvfile)
        assert len(data) == 1
        assert data[0]["Volume ID"] == "A12345"

        # simulate successful load with missing fields
        badcsvfile = tmp_path / "wrong.csv"
        badcsvfile.write_text("\n".join(["Item Type,Title,Source", "foo,bar,baz"]))
        with pytest.raises(CommandError) as err:
            cmd.load_csv(badcsvfile)
        assert "Volume ID column is required in CSV file" in str(err)

        # simulate invalid csv file
        with pytest.raises(CommandError) as err:
            badpath = "/bad/path/does/not/exist.csv"
            cmd.load_csv(badpath)
        assert f"Error loading the specified CSV file: {badpath}" in str(err)

    @override_settings(EEBO_DATA=FIXTURES_PATH)
    @patch("ppa.archive.management.commands.eebo_import.pymarc")
    @patch.object(DigitizedWork, "metadata_from_marc")
    def test_create_eebo_digwork(self, mock_metadata_from_marc, mock_pymarc, tmp_path):
        cmd = eebo_import.Command()
        cmd.eebo_data_path = tmp_path
        # create fake marc file for command to open
        (tmp_path / "A25820.mrc").open("w").write("not really marc")

        # minimal non-excerpt row
        datarow = {
            "Volume ID": "A25820",
            "Excerpt? Y/N": "N",
            "URL": "http://example.com/A12345",
            "Notes": "admin notes",
            "Author": "Aristotle",
            "Title": "A briefe of the art of rhetorique",
            # excerpt fields
            "Sort Titles (EXCERPT ONLY)": "briefe of the art of rhetorique",
            "Book/journal title (EXCERPT ONLY)": "some compendium",
            "Sequence number": "2-12",
            "Original page range": "ii-xii",
        }
        digwork = cmd.create_eebo_digwork(datarow)
        mock_marc_record = mock_pymarc.MARCReader.return_value.__next__()
        mock_metadata_from_marc.assert_called_with(mock_marc_record, populate=True)
        # should not set fields that are only set from csv for excerpts
        excerpt_fields = [
            "author",
            "title",
            "sort_title",
            "book_journal",
            "pages_digital",
            "pages_orig",
        ]
        for field in excerpt_fields:
            assert not getattr(digwork, field)

        # re-run, treating as an excerpt
        datarow["Excerpt? Y/N"] = "Y"
        digwork = cmd.create_eebo_digwork(datarow)
        assert digwork.item_type == DigitizedWork.EXCERPT
        assert digwork.author == datarow["Author"]
        assert digwork.title == datarow["Title"]
        assert digwork.sort_title == datarow["Sort Titles (EXCERPT ONLY)"]
        assert digwork.book_journal == datarow["Book/journal title (EXCERPT ONLY)"]
        assert digwork.pages_digital == datarow["Sequence number"]
        assert digwork.pages_orig == datarow["Original page range"]
