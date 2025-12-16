import pathlib

import polars as pl

NORMAL_VERBOSITY: int = 1


def check_pagecount(
    metadata_csv: pathlib.Path, pages_jsonl: pathlib.Path, verbosity: int = 1
):
    # check & report on page counts in the exported data

    # load metadata csv file
    meta_df = pl.read_csv(metadata_csv)
    # load page jsonlines (gzipped or not), group by work, and count # pages
    pages_pagecount_df = pl.read_ndjson(pages_jsonl).group_by("work_id").len()
    # check they are equal length (= same # of work ids)
    total_meta_works = len(meta_df)
    total_page_works = len(pages_pagecount_df)
    if total_meta_works == total_page_works:
        check_passed = True
    else:
        if verbosity >= NORMAL_VERBOSITY:
            print(
                f"Warning: mismatch between total works in metadata ({total_meta_works:,})"
                + f" and page data ({total_page_works:,})"
            )
    # join on work id to compare
    pagecount_compare_df = meta_df.join(pages_pagecount_df, on="work_id", how="left")
    # identify any works where the page count differs with actual page data
    pagecount_diff = pagecount_compare_df.filter(
        pl.col("len") != pl.col("page_count")
    ).with_columns(diff=pl.col("page_count").sub(pl.col("len")))

    total_pagecount_diff = len(pagecount_diff)
    if total_pagecount_diff == 0:
        check_passed = check_passed & True
    else:
        print(f"{total_pagecount_diff} works have page count discrepancies")
        # in increased verbosity mode, report on the works
        if verbosity > NORMAL_VERBOSITY:
            for work in pagecount_diff.iter_rows(named=True):
                print(
                    "  {work_id}: page_count {page_count}; {len} pages ({diff:+})".format(
                        **work
                    )
                )
