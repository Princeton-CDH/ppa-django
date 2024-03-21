# PPA Scripts

This directory contains stand-alone scripts associated with the Princeton
Prosody Archive that are not part of the web application proper.

At this time, these scripts do not have any additional requirements.

## HathiTrust "Version" Timestamps
This script extracts and saves the version timestamp information from the
public HathiTrust interface for a set of HathiTrust volumes. By default,
the set of volumes corresponds to PPA excerpt records (based on an exported
report).

- `get_version_labels.py`: The script to run. This script extracts HathiTrust
volume identifiers (htids) from a text file containing one htid per line. By
default, the input file is `ht-excerpts-2023-09-20.txt`, but an alternative file
can be specified as input. It writes its output as a tsv
with columns corresponding to htids and their extracted version timestamps.
    - input: Input `.txt` file. If none specified, `ht-excerpts-2023-09-20.txt`.
    - output: `version-labels/version-labels-[current date].tsv`
