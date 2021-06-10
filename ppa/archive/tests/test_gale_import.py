from collections import Counter
from unittest.mock import patch, Mock
from io import StringIO

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
import pytest

from ppa.archive.gale import GaleAPI, GaleAPIError
from ppa.archive.models import Collection, DigitizedWork
from ppa.archive.management.commands import gale_import


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
        assert "Imported 0; skipped 0; 0 errors; imported 0 pages." in output

    @override_settings(GALE_API_USERNAME="galeuser123")
    @patch("ppa.archive.management.commands.gale_import.Command.import_digitizedwork")
    @patch("ppa.archive.management.commands.gale_import.Command.load_collections")
    def test_import_csv(self, mock_load_collections, mock_import_digwork, tmp_path):
        csvfile = tmp_path / "test_import.csv"
        csvfile.write_text("\n".join(["ID,NOTES", "12345,brief mention in footnotes"]))

        stdout = StringIO()
        cmd = gale_import.Command(stdout=stdout)
        cmd.handle(ids=None, csv=csvfile)
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

    def test_import_digitizedwork_id(self):
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
            "pageResponse": {"pages": [
                {
                    "pageNumber": "0001",
                    "image": {"id": "09876001234567"}
                },
                {
                    "pageNumber": "0002",
                    "image": {"id": "09876001234568"}
                }
            ]},
        }
        test_id = "CW123456"
        digwork = cmd.import_digitizedwork(test_id)
        assert digwork
        assert isinstance(digwork, DigitizedWork)
        assert digwork.source_id == test_id
        assert digwork.title == "The life of Alexander Pope"
        assert digwork.author == "Owen Ruffhead"
        assert digwork.source == DigitizedWork.GALE
        assert digwork.page_count == 2
        cmd.gale_api.get_item.assert_called_with(test_id)

        # no collections should be associated
        assert digwork.collections.count() == 0

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

    @override_settings(GALE_API_USERNAME="galeuser123")
    def test_import_digitizedwork_csv(self):
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
            "pageResponse": {"pages": [
                {
                    "pageNumber": "0001",
                    "image": {"id": "09876001234567"}
                },
                {
                    "pageNumber": "0002",
                    "image": {"id": "09876001234568"}
                }
            ]}
        }
        test_id = "CW123456"
        csv_info = {
            'LIT': 'x',
            'MUS': 'x',
            'NOTES': 'just some mention in footnotes'
        }
        digwork = cmd.import_digitizedwork(test_id, **csv_info)
        assert csv_info['NOTES'] == digwork.notes
        literary = Collection.objects.get(name='Literary')
        music = Collection.objects.get(name='Music')
        assert digwork.collections.count() == 2
        assert literary in digwork.collections.all()
        assert music in digwork.collections.all()


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
        assert f'Error loading the specified CSV file: {badpath}' in str(err)

    @override_settings(GALE_API_USERNAME="galeuser123")
    @patch("ppa.archive.management.commands.gale_import.Command.import_digitizedwork")
    def test_call_command(self, mock_import_digwork):
        call_command('gale_import', '1234')
        assert mock_import_digwork.call_count == 1

    @override_settings()
    def test_config_error(self):
        del settings.GALE_API_USERNAME
        # ImproperlyConfigured api error should be raised as command error
        with pytest.raises(CommandError):
            gale_import.Command().handle(ids=[], csv=None)


