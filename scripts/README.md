# PPA Scripts

This directory contains stand-alone scripts associated with the Princeton
Prosody Archive that are not part of the web application proper.

At this time, these scripts do not have any additional requirements.

## HathiTrust "Version" Timestamps
This script extracts and saves the version timestamp information from the
public HathiTrust interface for PPA excerpt records (based on an exported report).

- `get_version_labels.py`: The script to run. It extracts the HathiTrust
volume identifiers (htids) from an existing excerpt file. It writes its output as a tsv
with columns corresponding to htids and their extracted version timestamps.
    - input (hard-coded): `ht-excerpts-2023-09-20.tsv` 
    - output: `version-labels/version-labels-[current date].tsv`
