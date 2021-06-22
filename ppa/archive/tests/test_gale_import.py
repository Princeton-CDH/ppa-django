from collections import Counter
from io import StringIO
from unittest.mock import Mock, patch

import pytest
from django import test
from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from ppa.archive.gale import GaleAPI, GaleAPIError, MARCRecordNotFound
from ppa.archive.management.commands import gale_import
from ppa.archive.models import Collection, DigitizedWork


@pytest.mark.django_db
class TestGaleImportCommand:
    @override_settings()
    def test_config_error(self):
        cmd = gale_import.Command()
        del settings.GALE_API_USERNAME
        with pytest.raises(CommandError):
            cmd.handle(ids=[], csv=None)

    @override_settings(GALE_API_USERNAME="galeuser123")
    @patch("ppa.archive.management.commands.gale_import.Command.import_digitizedwork")
    def test_import_ids(self, mock_import_digwork):
        stdout = StringIO()
        cmd = gale_import.Command(stdout=stdout)
        test_ids = ["abc1", "def2", "ghi3"]
        cmd.handle(ids=test_ids, csv=None)
        for item_id in test_ids:
            mock_import_digwork.assert_any_call(item_id)
        assert cmd.stats["total"] == 3
        output = stdout.getvalue()
        assert "Processed 3 items for import." in output
        # numbers are all 0 because import method was mocked
        assert (
            "Imported 0; 0 missing MARC records; skipped 0; 0 errors; imported 0 pages."
            in output
        )

    @override_settings(GALE_API_USERNAME="galeuser123")
    @patch("ppa.archive.management.commands.gale_import.Command.import_digitizedwork")
    @patch("ppa.archive.management.commands.gale_import.Command.load_collections")
    def test_import_csv(self, mock_load_collections, mock_import_digwork, tmp_path):
        csvfile = tmp_path / "test_import.csv"
        csvfile.write_text("\n".join(["ID,NOTES", "12345,brief mention in footnotes"]))

        stdout = StringIO()
        cmd = gale_import.Command(stdout=stdout)
        cmd.handle(ids=[], csv=csvfile)
        mock_import_digwork.assert_any_call("12345", NOTES="brief mention in footnotes")
        assert cmd.stats["total"] == 1
        output = stdout.getvalue()
        assert "Processed 1 item for import." in output
        mock_load_collections.assert_any_call()

    def test_load_collections(self):
        # create collections that are expected to exist
        Collection.objects.bulk_create(
            [
                Collection(name=value)
                for value in gale_import.Command.collection_codes.values()
            ]
        )
        cmd = gale_import.Command()
        cmd.load_collections()
        # collection lookup should be populated
        assert cmd.collections
        for code, name in cmd.collection_codes.items():
            assert isinstance(cmd.collections[code], Collection)
            assert cmd.collections[code].name == name

    @patch("ppa.archive.management.commands.gale_import.DigitizedWork.index_items")
    @patch(
        "ppa.archive.management.commands.gale_import.DigitizedWork.metadata_from_marc"
    )
    @patch("ppa.archive.management.commands.gale_import.get_marc_record")
    def test_import_digitizedwork_id(
        self, mock_get_marc_record, mock_metadata_from_marc, mock_index_items
    ):
        # import with id only
        cmd = gale_import.Command()
        # requires some setup included in handle
        cmd.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        cmd.digwork_contentype = ContentType.objects.get_for_model(DigitizedWork)
        cmd.gale_api = Mock(GaleAPI)
        cmd.stats = Counter()
        # simulate success
        cmd.gale_api.get_item.return_value = {
            "doc": {
                "title": "The life of Alexander Pope",
                "authors": ["Owen Ruffhead"],
                "isShownAt": "https://link.gale.co/test/ECCO?sid=gale_api&u=utopia9871",
                "citation": "Ruffhead, Owen. The life…, Accessed 8 June 2021.",
            },
            "pageResponse": {
                "pages": [
                    {"pageNumber": "0001", "image": {"id": "09876001234567"}},
                    {"pageNumber": "0002", "image": {"id": "09876001234568"}},
                ]
            },
        }
        test_id = "CW123456"
        cmd.id_lookup = {test_id: {"estc_id": "T012345"}}  # no volume
        digwork = cmd.import_digitizedwork(test_id)
        assert digwork
        assert isinstance(digwork, DigitizedWork)
        assert digwork.source_id == test_id
        assert digwork.title == "The life of Alexander Pope"
        assert digwork.source == DigitizedWork.GALE
        assert digwork.page_count == 2
        assert digwork.record_id == cmd.id_lookup[test_id]["estc_id"]
        assert not digwork.enumcron
        cmd.gale_api.get_item.assert_called_with(test_id)
        # should retrieve marc record and use to populate metadata
        mock_get_marc_record.assert_called_with(cmd.id_lookup[test_id]["estc_id"])
        mock_metadata_from_marc.assert_called_with(mock_get_marc_record.return_value)

        # no collections should be associated
        assert digwork.collections.count() == 0

        # work and pages should be indexed
        assert mock_index_items.call_count == 2

        # log entry should be created
        import_log = LogEntry.objects.get(object_id=digwork.pk)
        assert import_log.user_id == cmd.script_user.pk
        assert import_log.change_message == "Created from Gale API"
        assert import_log.action_flag == ADDITION

        # stats should be updated
        assert cmd.stats["imported"] == 1
        assert cmd.stats["pages"] == 2
        assert "skipped" not in cmd.stats
        assert "error" not in cmd.stats

    @patch("ppa.archive.management.commands.gale_import.DigitizedWork.index_items")
    @patch(
        "ppa.archive.management.commands.gale_import.DigitizedWork.metadata_from_marc"
    )
    @patch("ppa.archive.management.commands.gale_import.get_marc_record")
    @override_settings(GALE_API_USERNAME="galeuser123")
    def test_import_digitizedwork_csv(
        self, mock_get_marc_record, mock_metadata_from_marc, mock_index_items
    ):
        # simulate csv import with notes and collection membership
        cmd = gale_import.Command()
        # do some setup included in handle method
        cmd.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        cmd.digwork_contentype = ContentType.objects.get_for_model(DigitizedWork)
        cmd.gale_api = Mock(GaleAPI)
        cmd.stats = Counter()
        # create collections that are expected to exist
        Collection.objects.bulk_create(
            [
                Collection(name=value)
                for value in gale_import.Command.collection_codes.values()
            ]
        )
        cmd.load_collections()
        # simulate success
        cmd.gale_api.get_item.return_value = {
            "doc": {
                "title": "The life of Alexander Pope",
                "authors": ["Owen Ruffhead"],
                "isShownAt": "https://link.gale.co/test/ECCO?sid=gale_api&u=utopia9871",
                "citation": "Ruffhead, Owen. The life…, Accessed 8 June 2021.",
            },
            "pageResponse": {
                "pages": [
                    {"pageNumber": "0001", "image": {"id": "09876001234567"}},
                    {"pageNumber": "0002", "image": {"id": "09876001234568"}},
                ]
            },
        }
        test_id = "CW123456"
        cmd.id_lookup = {test_id: {"estc_id": "T012345", "volume": "2"}}
        csv_info = {"LIT": "x", "MUS": "x", "NOTES": "just some mention in footnotes"}
        digwork = cmd.import_digitizedwork(test_id, **csv_info)
        assert csv_info["NOTES"] == digwork.notes
        literary = Collection.objects.get(name="Literary")
        music = Collection.objects.get(name="Music")
        assert digwork.collections.count() == 2
        assert literary in digwork.collections.all()
        assert music in digwork.collections.all()
        assert digwork.enumcron == "2"

    def test_import_digitizedwork_error(self):
        # import with api error
        stderr = StringIO()
        cmd = gale_import.Command(stderr=stderr)
        cmd.gale_api = Mock(GaleAPI)
        cmd.stats = Counter()
        # use mock to simulate api error
        cmd.gale_api.get_item.side_effect = GaleAPIError
        digwork = cmd.import_digitizedwork("test_id")
        assert not digwork
        assert cmd.stats["error"] == 1
        for no_stat in ["skipped", "imported", "pages"]:
            assert no_stat not in cmd.stats
        output = stderr.getvalue()
        assert "Error getting item information for test_id" in output

    @patch("ppa.archive.management.commands.gale_import.get_marc_record")
    def test_import_digitizedwork_marc_notfound(self, mock_get_marc_record):
        mock_get_marc_record.side_effect = MARCRecordNotFound
        stderr = StringIO()
        cmd = gale_import.Command(stderr=stderr)
        # requires some setup included in handle
        cmd.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
        cmd.digwork_contentype = ContentType.objects.get_for_model(DigitizedWork)
        cmd.gale_api = Mock(GaleAPI)
        cmd.stats = Counter()
        test_id = "CW123456"
        cmd.id_lookup = {test_id: {"estc_id": "T012345"}}  # no volume
        # simulate success
        cmd.gale_api.get_item.return_value = {
            "doc": {
                "title": "The life of Alexander Pope",
                "authors": ["Owen Ruffhead"],
                "isShownAt": "https://link.gale.co/test/ECCO?sid=gale_api&u=utopia9871",
                "citation": "Ruffhead, Owen. The life…, Accessed 8 June 2021.",
            },
            "pageResponse": {
                "pages": [
                    {"pageNumber": "0001", "image": {"id": "09876001234567"}},
                    {"pageNumber": "0002", "image": {"id": "09876001234568"}},
                ]
            },
        }

        digwork = cmd.import_digitizedwork(test_id)
        assert digwork
        assert isinstance(digwork, DigitizedWork)
        assert digwork.record_id == cmd.id_lookup[test_id]["estc_id"]
        output = stderr.getvalue()
        assert "MARC record not found" in output
        mock_get_marc_record.assert_called_with(digwork.record_id)

    def test_import_digitizedwork_exists(self):
        # skip without api call if digwork already exists
        stderr = StringIO()
        digwork = DigitizedWork.objects.create(source_id="abc123")
        cmd = gale_import.Command(stderr=stderr)
        cmd.gale_api = Mock(GaleAPI)
        cmd.stats = Counter()
        imported = cmd.import_digitizedwork(digwork.source_id)
        assert not imported
        # should not call api if item is already in db
        assert cmd.gale_api.get_item.call_count == 0
        assert cmd.stats["skipped"] == 1
        for no_stat in ["error", "imported", "pages"]:
            assert no_stat not in cmd.stats

        output = stderr.getvalue()
        assert "already in the database; skipping" in output

    def test_load_csv(self, tmp_path):
        cmd = gale_import.Command()

        # simulate successful load and parse
        csvfile = tmp_path / "test_import.csv"
        csvfile.write_text(
            "\n".join(["ID,NOTES", "12345,brief mention in footnotes", "45678,"])
        )
        data = cmd.load_csv(csvfile)
        assert len(data) == 2
        assert data[0]["ID"] == "12345"

        # simulate successful load with invalid headers
        badcsvfile = tmp_path / "wrong.csv"
        badcsvfile.write_text("\n".join(["wrong,csv", "foo,bar"]))
        with pytest.raises(CommandError) as err:
            cmd.load_csv(badcsvfile)
        assert "ID column is required in CSV" in str(err)

        # simulate invalid csv file
        with pytest.raises(CommandError) as err:
            badpath = "/bad/path/does/not/exist.csv"
            cmd.load_csv(badpath)
        assert f"Error loading the specified CSV file: {badpath}" in str(err)

    @override_settings(GALE_API_USERNAME="galeuser123")
    @patch("ppa.archive.management.commands.gale_import.Command.import_digitizedwork")
    def test_call_command(self, mock_import_digwork):
        call_command("gale_import", "1234")
        assert mock_import_digwork.call_count == 1

    @override_settings()
    def test_config_error(self):
        del settings.GALE_API_USERNAME
        # ImproperlyConfigured api error should be raised as command error
        with pytest.raises(CommandError):
            gale_import.Command().handle(ids=[], csv=None)

    def test_call_with_csv_as_id(self):
        stdout = StringIO()
        gale_import.Command(stdout=stdout).handle(ids=["path/to/file.csv"], csv=None)
        output = stdout.getvalue()
        assert "not a valid id; did you forget to specify -c/--csv?" in output
