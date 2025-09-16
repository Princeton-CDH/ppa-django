import csv
import json
import os
import types
from collections import deque
from datetime import datetime, timedelta
from time import sleep
from unittest.mock import patch

import orjsonl
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from parasolr.django import SolrClient, SolrQuerySet

from ppa.archive.management.commands import generate_textcorpus
from ppa.archive.models import DigitizedWork, Page

# fixture test content; indexed by sample_works fixture
sample_page_content = [
    # text, tags
    ("something about dials and clocks", []),
    ("knobs and buttons", ["unusual_page"]),
    ("something else extra", ["local_ocr", "titlepage"]),
]


@pytest.fixture()
def sample_works(db):
    # load fixture works and index works and pages in Solr
    call_command("loaddata", "sample_digitized_works")
    # index in Solr
    DigitizedWork.index_items(DigitizedWork.objects.all())

    # add sample page content for one of the fixture works
    # and index it in solr
    # (copied from test_views)

    # use an unsaved digwork and hathi mock to index page data
    # using actual page indexing logic and fields
    digwork = DigitizedWork(source_id="chi.78013704")
    with patch.object(digwork, "hathi") as mockhathi:
        mock_pages = [
            {"content": content, "order": i + 1, "label": i, "tags": tags}
            for i, (content, tags) in enumerate(sample_page_content)
        ]
        mockhathi.page_data.return_value = mock_pages
        SolrClient().update.index(list(Page.page_index_data(digwork)))

    # NOTE: without a sleep, even with commit=True and/or low
    # commitWithin settings, indexed data isn't reliably available
    index_checks = 0
    while SolrQuerySet().search(item_type="work").count() == 0 and index_checks <= 10:
        # sleep until we get records back; 0.1 seems to be enough
        # for local dev with local Solr
        sleep(0.1)
        # to avoid infinite loop when there's something wrong here,
        # bail out after a certain number of attempts
        index_checks += 1
    yield
    # remove all records from solr
    SolrClient().update.delete_by_query("*:*")


def init_cmd(**kwargs):
    # initialize the textcorpus command and set options
    cmd = generate_textcorpus.Command()
    cmd.set_params(**kwargs)
    return cmd


def test_iter_solr_pages():
    cmd = init_cmd()
    page_data = cmd.iter_solr(item_type="page")
    assert isinstance(page_data, types.GeneratorType)
    page_data = list(page_data)
    # should return fixture pages but not works
    assert len(page_data) == len(sample_page_content)

    expected_page_fields = set(cmd.FIELDLIST["page"].keys())
    for i, result in enumerate(page_data):
        result_fields = set(result.keys())
        # solr doesn't return empty fields; first page has no tags
        if i == 0:
            result_fields.issubset(expected_page_fields)
        else:
            assert result_fields == expected_page_fields


def test_iter_solr_pages_mock(mock_solr_queryset):
    # mock so we can inspect call
    cmd = init_cmd()
    cmd.query_set = mock_solr_queryset()()
    # count is required for batching logic
    cmd.query_set.count.return_value = 10
    list(cmd.iter_solr(item_type="page"))
    # assertion needs to test after we begin/consume generator
    cmd.query_set.filter.assert_called_with(item_type="page")
    cmd.query_set.order_by.assert_called_with("id")
    cmd.query_set.only.assert_called_with(**cmd.FIELDLIST["page"])


def test_iter_solr_works(mock_solr_queryset):
    cmd = init_cmd()
    cmd.query_set = mock_solr_queryset()()
    # count is required for batching logic
    cmd.query_set.count.return_value = 10

    list(cmd.iter_solr(item_type="work"))

    # inspect query options
    # assertion needs to test after we begin/consume generator
    cmd.query_set.filter.assert_called_with(item_type="work")
    cmd.query_set.order_by.assert_called_with("id")
    cmd.query_set.only.assert_called_with(**cmd.FIELDLIST["work"])


@pytest.mark.django_db
def test_iter_works(sample_works):
    cmd = generate_textcorpus.Command()
    cmd.set_params()  # initialize solr queryset

    work_iter = cmd.iter_works()
    assert isinstance(work_iter, types.GeneratorType)

    solr_works = list(work_iter)
    # should match fixture data we indexed in setup fixture
    assert len(solr_works) == DigitizedWork.objects.count()
    expected_work_fields = set(cmd.FIELDLIST["work"].keys())
    for result in solr_works:
        result_fields = set(result.keys())
        # Solr doesn't return subtitle when empty;
        # only one fixture has a subtitle
        if result["source_id"] == "uc1.$b14645":
            # subtitle is present, but book journal and volume are not
            assert result_fields == expected_work_fields.difference(
                {"book_journal", "volume"}
            )
        else:
            assert result_fields.issubset(expected_work_fields)


@patch("ppa.archive.management.commands.generate_textcorpus.Command.iter_solr")
def test_iter_pages(mock_iter_solr):
    cmd = init_cmd()
    deque(cmd.iter_pages(), maxlen=0)
    mock_iter_solr.assert_called_with(item_type="page")


@patch("ppa.archive.management.commands.generate_textcorpus.progressbar")
def test_progressbar(mock_iter_progress, sample_works):
    # call the iterator and convert to list to consume
    list(init_cmd(progress=True, dry_run=True).iter_pages())
    mock_iter_progress.assert_called()

    mock_iter_progress.reset_mock()
    list(init_cmd(progressbar=False, dry_run=True).iter_pages())
    mock_iter_progress.assert_not_called()


def test_no_solr(empty_solr):
    cmd = init_cmd(verbosity=1, dry_run=True)
    with pytest.raises(CommandError, match="No page records found in Solr"):
        page_iter = cmd.iter_pages()
        deque(page_iter, maxlen=0)


def test_save_metadata(sample_works, tmp_path):
    # test against fixture data indexend in solr

    cmd = init_cmd(path=tmp_path, gzip=True)
    cmd.save_metadata()

    path_meta = tmp_path / "ppa_metadata.json"
    path_meta_csv = tmp_path / "ppa_metadata.csv"
    path_pages = tmp_path / "ppa_pages.jsonl"
    path_pages_gz = tmp_path / "ppa_pages.jsonl.gz"

    assert cmd.path_works_json == str(path_meta)
    assert cmd.path_works_csv == str(path_meta_csv)
    # compression enabled by default for pages jsonl
    assert cmd.path_pages_json == str(path_pages_gz)

    assert path_meta.exists()
    assert path_meta_csv.exists()
    assert not path_pages.exists()
    assert not path_pages_gz.exists()

    # load data to inspect results
    with open(path_meta) as f:
        json_meta = json.load(f)
    with open(path_meta_csv, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        csv_meta = list(reader)

    # check that we have the expected number of works
    expected_work_count = DigitizedWork.objects.all().count()
    assert len(csv_meta) == expected_work_count
    assert len(json_meta) == expected_work_count

    digworks = {digwork.index_id(): digwork for digwork in DigitizedWork.objects.all()}
    for json_data, csv_data in zip(json_meta, csv_meta):
        # get the work for this data based on work id
        digwork = digworks[json_data["work_id"]]
        # spot check a few fields
        assert json_data["source_id"] == digwork.source_id
        assert json_data["title"] == digwork.title
        assert json_data["sort_title"] == digwork.sort_title

        # a few fields vary in CSV and JSON output
        json_pubyear = json_data.pop("pub_year")
        # csv date is loaded as a string
        csv_pubyear = int(csv_data.pop("pub_year"))
        assert json_pubyear == digwork.pub_date
        assert csv_pubyear == digwork.pub_date
        # collections is a multi-value field;
        # JSON is a list; csv value is a delimited string
        json_collections = json_data.pop("collections")
        assert isinstance(json_collections, list)
        csv_collections = csv_data.pop("collections")
        # these should be equivalent once split
        assert json_collections == csv_collections.split(cmd.multival_delimiter)

        # assert enumcron (when present) is output as volume
        if digwork.enumcron:
            assert json_data["volume"] == digwork.enumcron
        else:
            # if not present, remove from csv for comparison with json
            csv_data.pop("volume")

        # no fixture works have book/journal field set
        # assert present, then remove before comparing the two versions
        assert "book_journal" in csv_data
        csv_data.pop("book_journal")

        # remaining data should match
        # solr and json omit empty fields; check and remove for comparison
        if not digwork.subtitle:
            # only one work has a subtitle
            csv_data.pop("subtitle")
        if not digwork.author:  # some sample fixture works have no author
            csv_data.pop("author")
        assert json_data == csv_data


def test_save_pages(sample_works, tmp_path):
    cmd = init_cmd(path=tmp_path)
    cmd.save_pages()
    # only creates pages and not metadata files
    assert not os.path.exists(cmd.path_works_json)
    assert not os.path.exists(cmd.path_works_csv)
    assert os.path.exists(cmd.path_pages_json)

    # check that output was generated as expected
    pages_json = orjsonl.load(cmd.path_pages_json)
    assert len(pages_json) == len(sample_page_content)

    for json_data, fixture_data in zip(pages_json, sample_page_content):
        # text content should match
        assert json_data["text"] == fixture_data[0]
        # tag content should match when present or be omitted
        if fixture_data[1]:
            assert json_data["tags"] == fixture_data[1]
        else:
            assert "tags" not in json_data


# test: options and expected resulting attributes on the command
test_options = [
    (
        {"path": "tmpdir_123", "gzip": False, "dry_run": True, "verbosity": 0},
        {
            "path": "tmpdir_123",
            "path_pages_json": "tmpdir_123/ppa_pages.jsonl",
            "is_dry_run": True,
            "verbosity": 0,
        },
    ),
    (
        {"gzip": True, "batch_size": 150, "progress": False},
        {
            "progress": False,
            "batch_size": 150,
            "path_pages_json__basename": "ppa_pages.jsonl.gz",
        },
    ),
]


@pytest.mark.parametrize("options,expected", test_options)
def test_set_params(options, expected, tmp_path):
    # initialize the command
    cmd = generate_textcorpus.Command()
    cmd.set_params(**options)

    for expected_attr, expected_value in expected.items():
        subpart = None
        # in one case we can only reliably test a portion of the value
        if "__" in expected_attr:
            expected_attr, subpart = expected_attr.split("__")

        attr_value = getattr(cmd, expected_attr)
        # can only reliably compare the basename of the pages filename
        if subpart == "basename":
            attr_value = os.path.basename(attr_value)

        assert attr_value == expected_value


@patch("ppa.archive.management.commands.generate_textcorpus.Command.iter_works")
@patch("ppa.archive.management.commands.generate_textcorpus.Command.iter_pages")
def test_default_args(mock_iter_works, mock_iter_pages, tmp_path):
    # testing default args requires running with call_commmand
    cmd = generate_textcorpus.Command()
    # change working directory to temp path to avoid accumulating empty
    # export directories in the project working director
    os.chdir(tmp_path)
    call_command(cmd)
    assert cmd.path == "ppa_corpus_" + generate_textcorpus.nowstr()
    assert cmd.doclimit is None
    assert cmd.verbosity == cmd.v_normal
    # compression for page output enabled by  default
    assert cmd.path_pages_json.endswith(".gz")
    assert cmd.batch_size == generate_textcorpus.DEFAULT_BATCH_SIZE


def test_handle(sample_works, tmp_path, capsys):
    output_dir = tmp_path / "output"
    cmd = generate_textcorpus.Command()
    # use call command so default args are set properly
    call_command(cmd, path=str(output_dir))
    assert cmd.path == str(output_dir)
    # output directory created
    assert output_dir.is_dir()
    # output files are created
    assert os.path.exists(cmd.path_works_json)
    assert os.path.exists(cmd.path_works_csv)
    assert os.path.exists(cmd.path_pages_json)
    # actual logic tested elsewhere

    captured = capsys.readouterr()
    assert captured.out == f"Saving files in {output_dir}\n"


@patch("ppa.archive.management.commands.generate_textcorpus.Command.iter_works")
@patch("ppa.archive.management.commands.generate_textcorpus.Command.iter_pages")
def test_dry_run(mock_iter_pages, mock_iter_works, tmp_path):
    # mock content does not matter in dry run, consumes generator but doesn't save
    mock_iter_works.return_value = [1, 2, 3, 4, 5]
    mock_iter_pages.return_value = ["a", "b", "c", "d"]

    output_path = tmp_path / "corpus"
    cmd = init_cmd()
    cmd.handle(path=output_path, dry_run=True, verbosity=1)

    assert cmd.path == output_path
    assert not os.path.exists(output_path)
    assert not os.path.exists(cmd.path_works_json)
    assert not os.path.exists(cmd.path_works_json)
    assert not os.path.exists(cmd.path_pages_json)


def test_nowstr():
    datetime_now = datetime.now()
    # Convert string date time to datetime object
    datetime_there = datetime.strptime(
        generate_textcorpus.nowstr(), generate_textcorpus.TIMESTAMP_FMT
    )
    time_diff = datetime_there - datetime_now
    assert time_diff < timedelta(seconds=5)
