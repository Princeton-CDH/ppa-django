from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.core.management import call_command
from django.core.management.base import CommandError

from ppa.archive.management.commands import hathi_excerpt
from ppa.archive.models import Collection, DigitizedWork


@pytest.mark.django_db
class TestHathiExcerptCommand:
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

    @patch(
        "ppa.archive.models.DigitizedWork.index_items"
    )  # don't index on page range change
    def test_excerpt_existing_work(self, mock_index_items):
        source_id = "abc.13245089"
        # create test collections
        coll1 = Collection.objects.create(name="One")
        coll2 = Collection.objects.create(name="Two")
        coll3 = Collection.objects.create(name="Three")
        # create test work; default source = hathitrust, item type = full work
        work = DigitizedWork.objects.create(
            source_id=source_id,
            title="Saturday review of literature",
            subtitle="arts, politics, and poetry",
            author="Else, Someone",
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
        # page count populated
        assert excerpt.page_count == 4
        # subtitle cleared
        assert not excerpt.subtitle

        # check that optional fields are blank
        for field in [
            "author",
            "pub_place",
            "publisher",
            "enumcron",
            "pages_orig",
            "notes",
            "public_notes",
        ]:
            assert getattr(excerpt, field) == ""
        # publication date is an integer field, so unset should be None
        assert excerpt.pub_date is None

        # check that log entry was created to document the change
        log = LogEntry.objects.get(object_id=excerpt.pk)
        assert log.action_flag == CHANGE
        assert log.change_message == "Converted to excerpt"
        assert log.user.username == "script"

        # index should be called once for pages, once for work
        assert mock_index_items.call_count == 2

    @patch("ppa.archive.models.DigitizedWork.index_items")
    def test_excerpt_no_existing_work(self, mock_index_items):
        source_id = "abc.98763134"
        cmd = hathi_excerpt.Command()
        cmd.setup()

        # test with all fields
        excerpt_info = {
            "Volume ID": source_id,
            "Item Type": "Excerpt",
            "Title": "Rhythm",
            "Sort Title": "Rhythm",
            "Book/Journal Title": "Saturday review of literature",
            "Digital Page Range": "10-13",
            "Record ID": "23445677",
            "Collection": "",
            "Author": "Kroeger, A. E",
            "Publication Date": 1872,
            "Publication Place": "Baltimore, MD",
            "Publisher": "Murdoch, Browne & Hill",
            "Enumcron": "v.11",
            "Original Page Range": "220-24",
            "Notes": "Original biblography",
            "Public Notes": "PERIODICAL",
        }
        cmd.excerpt(excerpt_info)
        # chould create a NEW work
        excerpt = DigitizedWork.objects.get(source_id=source_id)
        assert excerpt.item_type == DigitizedWork.EXCERPT
        assert excerpt.title == excerpt_info["Title"]
        assert excerpt.sort_title == excerpt_info["Sort Title"]
        assert excerpt.book_journal == excerpt_info["Book/Journal Title"]
        assert excerpt.pages_digital == excerpt_info["Digital Page Range"]
        assert excerpt.record_id == excerpt_info["Record ID"]
        assert excerpt.author == excerpt_info["Author"]
        assert excerpt.pub_date == excerpt_info["Publication Date"]
        assert excerpt.pub_place == excerpt_info["Publication Place"]
        assert excerpt.publisher == excerpt_info["Publisher"]
        assert excerpt.enumcron == excerpt_info["Enumcron"]
        assert excerpt.pages_orig == excerpt_info["Original Page Range"]
        assert excerpt.notes == excerpt_info["Notes"]
        assert excerpt.public_notes == excerpt_info["Public Notes"]
        # page count populated
        assert excerpt.page_count == 4

        # check that log entry was created to document the change
        log = LogEntry.objects.get(object_id=excerpt.pk)
        assert log.action_flag == ADDITION
        assert log.change_message == "Created via hathi_excerpt script"
        assert log.user.username == "script"

        # index should be called once for pages, once for work
        assert mock_index_items.call_count == 2

    def test_excerpt_parse_error(self):
        source_id = "abc.123-456"
        stderr = StringIO()
        cmd = hathi_excerpt.Command(stderr=stderr)
        cmd.setup()

        # required fields only, with an invalid digital page range
        excerpt_info = {
            "Volume ID": source_id,
            "Item Type": "Article",
            "Title": "Rhythm",
            "Sort Title": "Rhythm",
            "Book/Journal Title": "Saturday review of literature",
            "Digital Page Range": "100-13",
            "Record ID": "786544",
            "Collection": "",
        }
        cmd.excerpt(excerpt_info)
        assert cmd.stats["error"] == 1
        assert cmd.stats["created"] == 0
        error_output = stderr.getvalue()
        assert "Error saving %s" % source_id in error_output
        assert "start value should exceed stop (100-13)" in error_output

    @patch("ppa.archive.models.DigitizedWork.index_items")
    def test_call_commmand(self, mock_index_items, tmp_path):
        stdout = StringIO()
        # create minimal valid CSV with all required fields
        csvfile = tmp_path / "hathi_articles.csv"
        csvfile.write_text(
            "\n".join(
                [
                    "Item Type,Volume ID,Title,Sort Title,Book/Journal Title,Digital Page Range,Collection,Record ID",
                    "Article,abc.12345,About Rhyme,,Lit Review,10-12,,910192837",
                ]
            )
        )
        call_command("hathi_excerpt", csvfile, stdout=stdout)
        output = stdout.getvalue()
        assert "Excerpted 0 existing records" in output
        assert "created 1 new excerpt" in output
        assert "0 errors" in output
