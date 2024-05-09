#!/usr/bin/env python
"""
Use this script to extract a subset of EEBO-TCP P4 XML files from the
EEBO-TCP phase 1 and phase 2 data files.

Setup:

- Download EEBO-TCP phase 1 and 2 bulk files from https://textcreationpartnership.org/faq/#faq05
- Extract the contents of phase 1 and 2 zip files to a single directory; this
  should include the following files and directories:
  - IDnos_in_phase1.txt
  - IDnos_in_phase2.txt
  - P4_XML_TCP/
  - P4_XML_TCP_Ph2/
- Get a copy of EEBO MARC records from Proquest through your library;
  copy the complete marc file to your EEBO-TCP data directory as `eebo.mrc`
- Download EEBO-TCP mapping to MARC records at https://textcreationpartnership.org/using-tcp-content/eebo-tcp-cataloging-records/
- Extract to the same directory with EEBO-TCP content; expected file name
  is `IDmap.eebo_2015.xml`

"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract EEBO-TCP P4 XML files from zip files"
    )
    parser.add_argument(
        "input", help="CSV file with EEBO IDs to select as column 'Volume ID'"
    )
    parser.add_argument(
        "eebo_path", help="Path to location where EEBO-TCP content has been extracted"
    )
    parser.add_argument(
        "output", help="directory where the selected files should be saved"
    )
    args = parser.parse_args()

    # get a list of ids from the spreadsheet
    volume_ids = []
    with open(args.input) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            volume_ids.append(row["Volume ID"])

    # volume ids in our spreadsheet are in this format: A25820.0001.001
    # ids in phase1/phase2 correspond to the part before the first.
    # There are duplicates due to multiple excerpts from the same volume.
    base_ids = set([vol.split(".")[0] for vol in volume_ids])

    print(f"Exporting XML for {len(base_ids)} unique volumes to {args.output}")

    eebo_dir = Path(args.eebo_path)

    # determine which ids are phase 1 / 2 so we know where to look for them
    phase1_id_file = eebo_dir / "IDnos_in_phase1.txt"
    phase2_id_file = eebo_dir / "IDnos_in_phase2.txt"

    # read in phase 1 ids and identify volume ids to import from phase 1
    with phase1_id_file.open() as idfile:
        phase1_ids = set(idfile.read().splitlines())
        phase1_import = base_ids.intersection(phase1_ids)

    # same thing for phase 1
    with phase2_id_file.open() as idfile:
        phase2_ids = set(idfile.read().splitlines())
        phase2_import = base_ids.intersection(phase2_ids)

    output_path = Path(args.output)
    if not output_path.exists():
        output_path.mkdir()
    elif not output_path.is_dir():
        raise SystemExit(f"Output path {output_path} exists but is not a directory")

    phase1_xml = eebo_dir / "P4_XML_TCP"
    # group ids by file prefix
    phase1_file_ids = defaultdict(list)
    for volume_id in list(phase1_import):
        # zipfile name is based on first two letters of id, e.g. A0.zip
        prefix = volume_id[:2]
        phase1_file_ids[prefix].append(volume_id)

    phase1_count = 0
    for file_id, volume_ids in phase1_file_ids.items():
        # zipfile name is based on first two letters of id, e.g. A0.zip
        eebo_zipfile = phase1_xml / f"{file_id}.zip"

        with ZipFile(eebo_zipfile) as eebozip:
            for volume_id in volume_ids:
                xml_filename = f"{volume_id}.P4.xml"
                zip_xml_filename = f"{file_id}/{xml_filename}"
                # zipfile.extract would be convenient, but preserves
                # nested directory structure; export to a single directory
                with open(output_path / xml_filename, "wb") as outfile:
                    outfile.write(eebozip.read(zip_xml_filename))
                phase1_count += 1
    print(f"Exported {phase1_count} XML files from EEBO-TCP phase 1")

    # then do the same for phase 2
    phase2_xml = eebo_dir / "P4_XML_TCP_Ph2"
    # group ids by file prefix
    phase2_file_ids = defaultdict(list)
    for volume_id in list(phase2_import):
        # zipfile name is based on first two letters of id, e.g. A0.zip
        prefix = volume_id[:2]
        phase2_file_ids[prefix].append(volume_id)

    phase2_count = 0
    for file_id, volume_ids in phase2_file_ids.items():
        # zipfile name is based on first two letters of id, e.g. A0.zip
        eebo_zipfile = phase2_xml / f"{file_id}.zip"

        with ZipFile(eebo_zipfile) as eebozip:
            for volume_id in volume_ids:
                xml_filename = f"{volume_id}.P4.xml"
                zip_xml_filename = f"{file_id}/{xml_filename}"
                with open(output_path / xml_filename, "wb") as outfile:
                    outfile.write(eebozip.read(zip_xml_filename))
                phase2_count += 1

    print(f"Exported {phase2_count} XML files from EEBO-TCP phase 2")

    total_exported = phase1_count + phase2_count
    if total_exported == len(base_ids):
        print(f"Successfully exported all {total_exported} volumes")
    else:
        print(f"Only exported {total_exported} volumes...")
