import polars as pl

from ppa.dataset.validate import check_pagecount


def test_check_pagecount(tmp_path, capsys):
    meta_df = pl.DataFrame(data={"work_id": ["w1", "w2"], "page_count": [1, 2]})
    meta_csv_path = tmp_path / "meta.csv"
    meta_df.write_csv(meta_csv_path)
    # start with matching page count
    pages_df = pl.from_dicts(
        [
            # one page from work 1
            {"work_id": "w1", "text": "a b c"},
            # two pages from work 2
            {"work_id": "w2", "text": "d e f"},
            {"work_id": "w2", "text": "g h i"},
        ]
    )
    pages_json_path = tmp_path / "pages.json"
    # write as new-line delimited json
    pages_df.write_ndjson(pages_json_path)

    checks = check_pagecount(meta_csv_path, pages_json_path)
    # all checks pass
    assert all(checks)
    # non-verbose mode, so no output
    captured = capsys.readouterr()
    assert captured.out == ""

    # check passing verbose mode output
    check_pagecount(meta_csv_path, pages_json_path, verbose=True)
    captured = capsys.readouterr()
    assert "Total number of works matches" in captured.out
    assert "No discrepancies in page counts" in captured.out

    # force work count mismatch
    pages_plus_df = pages_df.extend(pl.from_dicts([{"work_id": "x1", "text": "x y z"}]))
    pages_plus_df.write_ndjson(pages_json_path)
    checks = check_pagecount(meta_csv_path, pages_json_path)
    assert checks == [False, True]  # work count not ok, page count ok
    captured = capsys.readouterr()
    assert "Total works in metadata does not match page data" in captured.out

    # force page count mismatch
    missing_pages_df = pages_df.limit(2)
    missing_pages_df.write_ndjson(pages_json_path)
    checks = check_pagecount(meta_csv_path, pages_json_path)
    assert checks == [True, False]  # work count ok, page count not ok
    captured = capsys.readouterr()
    assert "1 work with page count discrepancy" in captured.out
    # detailed info not present if verbose output not requested
    assert "w2: page_count 2; 1 pages (+1)" not in captured.out

    # now check with verbose output
    check_pagecount(meta_csv_path, pages_json_path, verbose=True)
    captured = capsys.readouterr()
    assert "w2: page_count 2; 1 pages (+1)" in captured.out
