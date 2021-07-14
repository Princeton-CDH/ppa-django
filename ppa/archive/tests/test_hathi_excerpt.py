from unittest.mock import patch

import pytest
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.core.management.base import CommandError

from ppa.archive.management.commands import hathi_excerpt
from ppa.archive.models import Collection, DigitizedWork


@pytest.mark.django_db
class TestHathiExcerptCommand:
    # @override_settings()
    # def test_config_error(self):
    #     cmd = gale_import.Command()
    #     del settings.GALE_API_USERNAME
    #     with pytest.raises(CommandError):
    #         cmd.handle(ids=[], csv=None)

    def test_load_collections(self):
        # create test collections
        collections = ["Grab bag", "Junk drawer"]
        Collection.objects.bulk_create(
            [Collection(name=value) for value in collections]
        )
        cmd = hathi_excerpt.Command()
        cmd.load_collections()
        # collection lookup should be populated
        assert cmd.collections
        for name in collections:
            assert isinstance(cmd.collections[name], Collection)
            assert cmd.collections[name].name == name

    def test_load_csv(self, tmp_path):
        cmd = hathi_excerpt.Command()
        # simulate successful load and parse of CSV with all required fields
        csvfile = tmp_path / "hathi_articles.csv"
        csvfile.write_text(
            "\n".join(
                [
                    "Item Type,Volume ID,Title,Sort Title,Book/Journal Title,Digital Page Range,Collection,Record ID",
                    "Article,abc.12345,About Rhyme",
                ]
            )
        )
        data = cmd.load_csv(csvfile)
        assert len(data) == 1
        assert data[0]["Volume ID"] == "abc.12345"

        # simulate successful load with missing fields
        badcsvfile = tmp_path / "wrong.csv"
        badcsvfile.write_text("\n".join(["Item Type,Volume ID,Title,", "foo,bar,baz"]))
        with pytest.raises(CommandError) as err:
            cmd.load_csv(badcsvfile)
        assert "Missing required fields in CSV file" in str(err)
        # error message should include the missing required fields; check a couple
        assert "Sort Title" in str(err)
        assert "Digital Page Range" in str(err)

        # simulate invalid csv file
        with pytest.raises(CommandError) as err:
            badpath = "/bad/path/does/not/exist.csv"
            cmd.load_csv(badpath)
        assert f"Error loading the specified CSV file: {badpath}" in str(err)

    @patch("ppa.archive.models.DigitizedWork.index_items")
    def test_excerpt_existing_work(self, mock_index_items):
        source_id = "abc:13245089"
        # create test collections
        coll1 = Collection.objects.create(name="One")
        coll2 = Collection.objects.create(name="Two")
        coll3 = Collection.objects.create(name="Three")
        # create test work; default source = hathitrust, item type = full work
        work = DigitizedWork.objects.create(
            source_id=source_id, title="Saturday review of literature"
        )
        # associate with collection 1
        work.collections.add(coll1)

        cmd = hathi_excerpt.Command()
        cmd.setup()

        # test with required fields only
        excerpt_info = {
            "Volume ID": source_id,
            "Item Type": "Article",
            "Title": "Rhythm",
            "Sort Title": "Rhythm",
            "Book/Journal Title": "Saturday review of literature",
            "Digital Page Range": "10-13",
            "Record ID": "786544",
            "Collection": "Two;Three",
        }
        cmd.excerpt(excerpt_info)
        # inspect the newly-excerpted work; get a fresh copy from the db
        excerpt = DigitizedWork.objects.get(pk=work.pk)
        assert excerpt.item_type == DigitizedWork.ARTICLE
        assert excerpt.title == excerpt_info["Title"]
        assert excerpt.sort_title == excerpt_info["Sort Title"]
        assert excerpt.book_journal == excerpt_info["Book/Journal Title"]
        assert excerpt.pages_digital == excerpt_info["Digital Page Range"]
        assert excerpt.record_id == excerpt_info["Record ID"]
        # spreadsheet collection membership should replace any existing association
        assert excerpt.collections.count() == 2
        assert set(c.name for c in excerpt.collections.all()) == set(["Two", "Three"])

        # check that log entry was created to document the change
        log = LogEntry.objects.get(object_id=excerpt.pk)
        assert log.action_flag == CHANGE
        assert log.change_message == "Converted to excerpt"
        assert log.user.username == "script"
