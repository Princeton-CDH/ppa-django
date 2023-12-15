from unittest.mock import patch
import pytest
from collections import deque
import types
from django.core.management import call_command
from django.core.management.base import CommandError
from datetime import datetime, timedelta
import os
import random
import orjsonl
import csv
import json
import tempfile
from ppa.archive.management.commands import generate_textcorpus

mock_work_docs = [
    {
        "work_id": "text1",
        "source_id": "source1",
        "cluster_id": "cluster1",
        "title": "title",
        "author": "author_exact",
        "pub_year": "pub_date",
        "publisher": "publisher",
        "pub_place": "pub_place",
        "collections": "collections_exact",
        "work_type": "work_type_s",
        "source": ["Gale"],
        "source_url": "source_url",
        "sort_title": "sort_title",
        "subtitle": "subtitle",
    },
    {
        "work_id": "text2",
        "source_id": "source1",
        "cluster_id": "cluster_id_s",
        "title": "title",
        "author": "author_exact",
        "pub_year": "pub_date",
        "publisher": "publisher",
        "pub_place": "pub_place",
        "collections": "collections_exact",
        "work_type": "work_type_s",
        "source": ["Hathi"],
        "source_url": "source_url",
        "sort_title": "sort_title",
        "subtitle": "subtitle",
    },
    {
        "work_id": "text3",
        "source_id": "source_id",
        "cluster_id": "cluster_id_s",
        "title": "title",
        "author": "author_exact",
        "pub_year": "pub_date",
        "publisher": "publisher",
        "pub_place": "pub_place",
        "collections": "collections_exact",
        "work_type": "work_type_s",
        "source": "source_t",
        "source_url": "source_url",
        "sort_title": "sort_title",
        "subtitle": "subtitle",
    },
]
mock_work_docs_copy = [{**d} for d in mock_work_docs]

mock_page_docs = [
    {
        "id": "text1.000001",
        "work_id": "text1",
        "num": 0,
        "num_orig": "label",
        "tags": "tags",
        "text": "content",
    },
    {
        "id": "text1.000002",
        "work_id": "text1",
        "num": 1,
        "num_orig": "label",
        "tags": ["tags"],
        "text": "content",
    },
    {
        "id": "text2.00001",
        "work_id": "group_id_s",
        "num": 2,
        "num_orig": "label",
        "tags": ["tags"],
        "text": "content",
    },
    {
        "id": "text2.00002",
        "work_id": "group_id_s",
        "num": 3,
        "num_orig": "label",
        "tags": ["tags"],
        "text": "content",
    },
]

# need this because dicts are altered
mock_page_docs_copy = [{**d} for d in mock_page_docs]


def init_cmd(**kwargs):
    cmd = generate_textcorpus.Command()
    cmd.set_params(**kwargs)
    return cmd


@pytest.fixture
def patched_works_solr_queryset(mock_solr_queryset):
    # local fixture that uses parasolr queryset mock
    # and patches in test docs & facets
    with patch(
        "ppa.archive.management.commands.generate_textcorpus.SolrQuerySet",
        new=mock_solr_queryset(),
    ) as mock_queryset_cls:
        mock_qs = mock_queryset_cls.return_value
        mock_qs.only.return_value.count.return_value = len(mock_work_docs)
        mock_qs.only.return_value.__getitem__.return_value = mock_work_docs
        yield mock_qs


@pytest.fixture
def patched_pages_solr_queryset(mock_solr_queryset):
    # local fixture that uses parasolr queryset mock
    # and patches in test docs & facets
    with patch(
        "ppa.archive.management.commands.generate_textcorpus.SolrQuerySet",
        new=mock_solr_queryset(),
    ) as mock_queryset_cls:
        mock_qs = mock_queryset_cls.return_value
        mock_qs.only.return_value.count.return_value = len(mock_page_docs)
        mock_qs.only.return_value.__getitem__.return_value = mock_page_docs
        yield mock_qs


def test_iter_solr_pages(patched_pages_solr_queryset):
    with tempfile.TemporaryDirectory() as tdir:
        cmd = init_cmd(path=tdir)
        page_iter = cmd.iter_solr()
        assert isinstance(page_iter, types.GeneratorType)

        for i, d in enumerate(page_iter):
            assert type(d) is dict
            assert d
            assert set(d.keys()) == set(cmd.PAGE_FIELDLIST.keys())
            assert d["id"]
            assert "." in d["id"]
            assert d["id"].split(".")[-1].isdigit()

        assert i + 1 == len(mock_page_docs)

        # assertion needs to test after we begin/consume generator
        cmd.query_set.filter.assert_called_with(item_type="page")
        cmd.query_set.order_by.assert_called_with("id")
        cmd.query_set.only.assert_called_with(**cmd.PAGE_FIELDLIST)


def test_iter_solr_works(patched_works_solr_queryset):
    with tempfile.TemporaryDirectory() as tdir:
        cmd = init_cmd(path=tdir)

        work_iter = cmd.iter_solr(item_type="work")
        assert isinstance(work_iter, types.GeneratorType)

        for i, d in enumerate(work_iter):
            assert type(d) is dict
            assert d
            assert set(d.keys()) == set(cmd.WORK_FIELDLIST.keys())
            assert d["work_id"]

        assert i + 1 == len(mock_work_docs)

        # assertion needs to test after we begin/consume generator
        cmd.query_set.filter.assert_called_with(item_type="work")
        cmd.query_set.order_by.assert_called_with("id")
        cmd.query_set.only.assert_called_with(**cmd.WORK_FIELDLIST)


def test_iter_works():
    with patch(
        "ppa.archive.management.commands.generate_textcorpus.Command.iter_solr"
    ) as mock_iter_solr:
        mock_iter_solr.return_value = (d for d in mock_work_docs)
        cmd = generate_textcorpus.Command()

        work_iter = cmd.iter_works()
        assert isinstance(work_iter, types.GeneratorType)

        res = list(work_iter)
        assert res, "No pages returned"
        assert len(res) == len(mock_work_docs)
        for d in res:
            assert type(d["source"]) is str, "string conversion failed"
        mock_iter_solr.assert_called_with(item_type="work")


def test_iter_pages():
    with patch(
        "ppa.archive.management.commands.generate_textcorpus.Command.iter_solr"
    ) as mock_iter_solr:
        mock_iter_solr.return_value = (d for d in mock_page_docs)
        cmd = init_cmd()
        page_iter = cmd.iter_pages()
        assert isinstance(page_iter, types.GeneratorType)

        res = list(page_iter)
        assert res, "No pages returned"
        assert len(res) == len(mock_page_docs)
        mock_iter_solr.assert_called_with(item_type="page")


def test_progressbar(patched_pages_solr_queryset):
    with patch(
        "ppa.archive.management.commands.generate_textcorpus.progressbar"
    ) as mock_iter_progress:
        cmd = init_cmd(verbosity=1, dry_run=True)
        page_iter = cmd.iter_pages()
        deque(page_iter, maxlen=0)
        mock_iter_progress.assert_called()

    with patch(
        "ppa.archive.management.commands.generate_textcorpus.progressbar"
    ) as mock_iter_progress:
        cmd = init_cmd(verbosity=0, dry_run=True)
        page_iter = cmd.iter_pages()
        deque(page_iter, maxlen=0)
        mock_iter_progress.assert_not_called()


def test_no_solr():
    cmd = init_cmd(verbosity=1, dry_run=True)
    with pytest.raises(CommandError):
        page_iter = cmd.iter_pages()
        deque(page_iter, maxlen=0)


def test_save_metadata():
    with patch(
        "ppa.archive.management.commands.generate_textcorpus.Command.iter_solr"
    ) as mock_iter_solr:
        mock_iter_solr.return_value = (d for d in mock_work_docs)

        with tempfile.TemporaryDirectory() as tdir:
            cmd = init_cmd(path=tdir)
            assert cmd.path == tdir
            cmd.save_metadata()

            path_meta = os.path.join(tdir, "ppa_metadata.json")
            path_meta_csv = os.path.join(tdir, "ppa_metadata.csv")
            path_pages = os.path.join(tdir, "ppa_pages.jsonl")
            path_pages_gz = os.path.join(tdir, "ppa_pages.jsonl.gz")

            assert cmd.path_meta == path_meta
            assert cmd.path_meta_csv == path_meta_csv
            assert cmd.path_texts == (path_pages if cmd.uncompressed else path_pages_gz)

            assert os.path.exists(path_meta)
            assert os.path.exists(path_meta_csv)
            assert not os.path.exists(path_pages)
            assert not os.path.exists(path_pages_gz)

            with open(path_meta) as f:
                json_meta = json.load(f)

            with open(path_meta_csv, newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                csv_meta = list(reader)

            meta_ld_out = list(cmd.iter_works())
            assert len(meta_ld_out) == 0, "generator should be consumed"

            assert len(json_meta) == len(csv_meta)
            assert len(json_meta) == len(mock_work_docs)

            for json_d, csv_d, mock_d in zip(json_meta, csv_meta, mock_work_docs_copy):
                assert json_d == csv_d
                assert json_d["work_id"] == mock_d["work_id"]
                assert json_d["source"] != mock_d["source"]

        mock_iter_solr.assert_called_with(item_type="work")


def test_save_pages():
    with patch(
        "ppa.archive.management.commands.generate_textcorpus.Command.iter_solr"
    ) as mock_iter_solr:
        mock_iter_solr.return_value = (d for d in mock_page_docs)

        with tempfile.TemporaryDirectory() as tdir:
            cmd = init_cmd(path=tdir)
            assert cmd.path == tdir
            cmd.save_pages()
            assert not os.path.exists(cmd.path_meta)
            assert not os.path.exists(cmd.path_meta_csv)
            assert os.path.exists(cmd.path_texts)

            pages_ld_out = list(cmd.iter_pages())
            assert len(pages_ld_out) == 0, "generator should be spent"

            pages_json = orjsonl.load(cmd.path_texts)
            assert len(pages_json) == len(mock_page_docs)

            for json_d, mock_d in zip(pages_json, mock_page_docs_copy):
                assert json_d["id"] == mock_d["id"]
                assert json_d == mock_d  # no change, keys were same


def test_set_params():
    with tempfile.TemporaryDirectory() as tdir1, tempfile.TemporaryDirectory() as tdir2:
        alloptiond = {
            "path": [tdir1, tdir2],
            "no_gzip": [True, False],
            "dry_run": [True, False],
            "doc_limit": [0, 1000],
            "verbosity": [0, 1],
            "batch_size": [1000, 10000],
        }
        cmd = init_cmd()
        for run in range(10):
            optiond = {
                optname: random.choice(opts) for optname, opts in alloptiond.items()
            }
            cmd.set_params(**optiond)
            assert cmd.path == optiond["path"]
            assert cmd.uncompressed == optiond["no_gzip"]
            assert cmd.is_dry_run == optiond["dry_run"]
            assert (
                cmd.doclimit is None
                if not optiond["doc_limit"]
                else optiond["doc_limit"]
            )
            assert cmd.verbose == bool(optiond["verbosity"] > 1)
            assert cmd.progress == bool(optiond["verbosity"] > 0)
            assert (
                cmd.batch_size == optiond["batch_size"]
                if optiond["batch_size"]
                else generate_textcorpus.DEFAULT_BATCH_SIZE
            )


def test_default_args(patched_works_solr_queryset):
    herenow = os.getcwd()
    with tempfile.TemporaryDirectory() as tdir:
        os.chdir(tdir)
        cmd = init_cmd()
        assert cmd.path == "ppa_corpus_" + generate_textcorpus.nowstr()
        assert not cmd.doclimit
        assert not cmd.verbose
        assert not cmd.uncompressed
        assert cmd.batch_size == generate_textcorpus.DEFAULT_BATCH_SIZE
    os.chdir(herenow)


def test_invalid_args(tmpdir):
    # Flags that are not supported
    with pytest.raises(CommandError):
        call_command(
            "generate_textcorpus", "--path", tmpdir.dirpath(), "--doc-limit", "one"
        )

    with pytest.raises(CommandError):
        call_command(
            "generate_textcorpus", "--path", tmpdir.dirpath(), "--batch-size", "two"
        )

    with pytest.raises(CommandError):
        call_command(
            "generate_textcorpus", "--path", tmpdir.dirpath(), "--woops", "huh"
        )


def test_handle():
    with (
        patch(
            "ppa.archive.management.commands.generate_textcorpus.Command.iter_works",
        ) as mock_iter_works,
        patch(
            "ppa.archive.management.commands.generate_textcorpus.Command.iter_pages",
        ) as mock_iter_pages,
    ):
        mock_iter_works.return_value = (d for d in mock_work_docs)
        mock_iter_pages.return_value = (d for d in mock_page_docs)

        with tempfile.TemporaryDirectory() as tdir:
            cmd = init_cmd()
            cmd.handle(path=tdir, verbosity=1)
            assert cmd.path == tdir
            assert os.path.exists(cmd.path_meta)
            assert os.path.exists(cmd.path_meta_csv)
            assert os.path.exists(cmd.path_texts)

            meta_ld_out = list(cmd.iter_pages())
            assert len(meta_ld_out) == 0, "generator should be spent"

            with open(cmd.path_meta) as f:
                json_meta = json.load(f)

            with open(cmd.path_meta_csv, newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                csv_meta = list(reader)

            assert len(json_meta) == len(csv_meta)
            assert len(json_meta) == len(mock_work_docs)

            for json_d, csv_d, mock_d in zip(json_meta, csv_meta, mock_work_docs_copy):
                assert json_d == csv_d
                assert json_d["work_id"] == mock_d["work_id"]
                assert json_d["source"] != mock_d["source"]

            pages_ld_out = list(cmd.iter_pages())
            assert len(pages_ld_out) == 0, "generator should be spent"

            pages_json = orjsonl.load(cmd.path_texts)
            assert len(pages_json) == len(mock_page_docs)

            for json_d, mock_d in zip(pages_json, mock_page_docs_copy):
                assert json_d["id"] == mock_d["id"]
                assert json_d == mock_d  # no change, keys were same


def test_dry_run():
    with (
        patch(
            "ppa.archive.management.commands.generate_textcorpus.Command.iter_works",
        ) as mock_iter_works,
        patch(
            "ppa.archive.management.commands.generate_textcorpus.Command.iter_pages",
        ) as mock_iter_pages,
    ):
        mock_iter_works.return_value = (d for d in mock_work_docs)
        mock_iter_pages.return_value = (d for d in mock_page_docs)

        with tempfile.TemporaryDirectory() as tdir:
            path = os.path.join(tdir, "corpus")
            cmd = init_cmd()
            cmd.handle(path=path, dry_run=True, verbosity=1)
            assert cmd.path == path
            assert not os.path.exists(path)
            assert not os.path.exists(cmd.path_meta)
            assert not os.path.exists(cmd.path_meta_csv)
            assert not os.path.exists(cmd.path_texts)


def test_nowstr():
    datetime_now = datetime.now()
    # Convert string date time to datetime object
    datetime_there = datetime.strptime(
        generate_textcorpus.nowstr(), generate_textcorpus.TIMESTAMP_FMT
    )
    time_diff = datetime_there - datetime_now
    assert time_diff < timedelta(seconds=5)
