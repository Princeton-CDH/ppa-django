"""
Extract version labels from HathiTrust volume pages.
"""
import sys
import os.path
import re
import time
import datetime
import requests


def get_version_label(htid):
    """
    Extract the HathiTrust "version label" from a record's catalog page.
    Returns the corresponding timestamp, returns None if the HTTP request fails.
    """
    # a script block in HT record page includes a number of HT.params including version timestamp
    re_pattern = r'HT.params.versionLabel = "([^"]+)";'
    catalog_url = f"https://hdl.handle.net/2027/{htid}"
    r = requests.get(catalog_url, timeout=5)
    if r.status_code == requests.codes['ok']:
        # Extract version_label from response text
        version_label = re.findall(re_pattern, r.text)
        if version_label:
            return version_label[0]
        else:
            print(f"Warning: {htid} missing versionLabel!")
    else:
        print(f"Warning: bad/unexpected response")


def get_version_labels(htids, wait_time=1):
    """
    Extracts the HathiTrust "version label" for each record within htids.
    Returns a list of the extracted htid-timestamp pairs.
    """
    version_pairs = []
    n_skipped = 0
    n_htids = len(htids)
    for i, htid in enumerate(htids):
        if i:
            # Wait wait_time seconds between requests
            time.sleep(wait_time)
            # show progress
        if i % 10 == 0:
            print(f"Progress: {i}/{n_htids}")
        version_label = get_version_label(htid)
        if version_label:
            version_pairs.append((htid, version_label))
        else:
            n_skipped += 1
    if n_skipped:
        print(f"Warning: Failed to gather versions for {n_skipped} volumes")
    return version_pairs


if __name__ == "__main__":
    if len(sys.argv) not in [1,2]:
        print("Usage: ([htids list])")
        sys.exit(1)

    # Check if an input file has been provided
    in_tsv = "ht-excerpts-2023-09-20.txt" # Default value
    if len(sys.argv) == 3:
        in_tsv = sys.argv[1]

    out_tsv = f"version-labels/version-labels-{datetime.date.today()}.tsv"

    # Get htids
    htids = []
    with open(in_tsv) as reader:
        for line in reader:
            htid = line.strip()
            htids.append(htid)
    version_pairs = get_version_labels(htids)

    # Write version labels to file
    with open(out_tsv, mode='w') as writer:
        writer.write(f"htid\tversion_label\n")
        for htid, version_label in version_pairs:
            writer.write(f"{htid}\t{version_label}\n")
