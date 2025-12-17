import pathlib

import polars as pl

app_dir = pathlib.Path(__file__).parent
data_package_path = app_dir / "ppa_datapackage.json"


def check_pagecount(
    metadata_csv: pathlib.Path, pages_jsonl: pathlib.Path, verbose: bool = False
) -> list[bool]:
    """
    Check that work and page counts match in the exported metadata and page data.
    Returns a list of boolean values indicating the status of the checks:
    - total works match
    - page counts match
    """
    checks = []

    # load metadata csv file
    meta_df = pl.read_csv(metadata_csv)
    # load page json lines (gzipped or not); group by work, and count # pages
    pages_pagecount_df = pl.read_ndjson(pages_jsonl).group_by("work_id").len()
    # check they are equal length (= same # of work ids)
    total_meta_works = len(meta_df)
    total_page_works = len(pages_pagecount_df)
    total_works_ok = False
    if total_meta_works == total_page_works:
        total_works_ok = True
        if verbose:
            print(
                "✅ Total number of works matches "
                + f"(metadata + page data; {total_meta_works})"
            )
    else:
        print(
            "❌ Total works in metadata does not match page data "
            + f"({total_meta_works:,}, {total_page_works:,})"
        )
    checks.append(total_works_ok)

    # join on work id to compare
    pagecount_compare_df = meta_df.join(pages_pagecount_df, on="work_id", how="left")
    # identify any works where the page count differs with actual page data
    pagecount_diff = pagecount_compare_df.filter(
        pl.col("len") != pl.col("page_count")
    ).with_columns(diff=pl.col("page_count").sub(pl.col("len")))

    total_pagecount_diff = len(pagecount_diff)
    pagecount_ok = False
    if total_pagecount_diff == 0:
        pagecount_ok = True
        if verbose:
            print("✅ No discrepancies in page counts")
    else:
        plural = "s" if total_pagecount_diff != 1 else ""
        print(f"{total_pagecount_diff} work{plural} with page count discrepancy")
        # in increased verbosity mode, report on the works
        if verbose:
            for work in pagecount_diff.iter_rows(named=True):
                print(
                    "  {work_id}: page_count {page_count}; {len} pages ({diff:+})".format(
                        **work
                    )
                )
    checks.append(pagecount_ok)

    return checks
