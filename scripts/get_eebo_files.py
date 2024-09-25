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

Example usage::

    ./scripts/get_eebo_files.py eebo_works.csv data/eebo_tcp/ /tmp/eebo

"""

import argparse
import csv
from collections import defaultdict
from os.path import basename
from pathlib import Path
from zipfile import ZipFile

from lxml import objectify
import pymarc


def group_ids(idlist: list) -> dict[str, list]:
    # given a list of of EEBO-TCP ids, return a dictionary of lists
    # keyed on first two letters of id.
    # zipfile names are based on first two letters of id, e.g. A0.zip
    grouped_ids = defaultdict(list)
    for volume_id in idlist:
        prefix = volume_id[:2]
        grouped_ids[prefix].append(volume_id)

    return grouped_ids


def extract_from_zipfile(
    zipfilename: str, extract_list: list, output_path: Path
) -> int:
    """Takes a path to zipfile, a list of files in that zip to extract,
    and an output path where files should be extracted. Writes
    files to a single directory without nesting.
    Returns a count of the number of files extracted.
    """
    count = 0
    with ZipFile(zipfilename) as eebozip:
        for extract_path in extract_list:
            # zipfile.extract would be convenient, but preserves
            # nested directory structure; we want to export to a single directory
            # paths inside the zip file are nested, but we want to extract
            # to a single directory; use full path to read, basename to write
            output_name = basename(extract_path)
            with open(output_path / output_name, "wb") as outfile:
                outfile.write(eebozip.read(extract_path))
            count += 1
    return count


def extract_xml_files(eebo_path: Path, base_ids: list, output_path: Path):
    print(f"Exporting XML for {len(base_ids)} unique volumes to {output_path}")

    # make sure we can use the specified output path
    if not output_path.exists():
        output_path.mkdir()
    elif not output_path.is_dir():
        raise SystemExit(f"Output path {output_path} exists but is not a directory")

    # determine which ids are phase 1 / 2 so we know where to look for them
    phase1_id_file = eebo_path / "IDnos_in_phase1.txt"
    phase2_id_file = eebo_path / "IDnos_in_phase2.txt"

    # read in phase 1 ids and identify volume ids to import from phase 1
    with phase1_id_file.open() as idfile:
        phase1_ids = set(idfile.read().splitlines())
        phase1_import = base_ids.intersection(phase1_ids)

    # same thing for phase 1
    with phase2_id_file.open() as idfile:
        phase2_ids = set(idfile.read().splitlines())
        phase2_import = base_ids.intersection(phase2_ids)

    phase1_xml = eebo_path / "P4_XML_TCP"
    phase2_xml = eebo_path / "P4_XML_TCP_Ph2"
    # group ids by file prefix for easy matching with zip file names
    phase1_file_ids = group_ids(list(phase1_import))
    phase2_file_ids = group_ids(list(phase2_import))

    phase1_count = 0
    for file_id, volume_ids in phase1_file_ids.items():
        # zipfile name is based on first two letters of id, e.g. A0.zip
        eebo_zipfile = phase1_xml / f"{file_id}.zip"
        extract_files = [f"{file_id}/{volume_id}.P4.xml" for volume_id in volume_ids]
        phase1_count += extract_from_zipfile(eebo_zipfile, extract_files, output_path)
    print(f"Exported {phase1_count} XML files from EEBO-TCP phase 1")

    phase2_count = 0
    for file_id, volume_ids in phase2_file_ids.items():
        # zipfile name is based on first two letters of id, e.g. A0.zip
        eebo_zipfile = phase2_xml / f"{file_id}.zip"
        extract_files = [f"{file_id}/{volume_id}.P4.xml" for volume_id in volume_ids]
        phase2_count += extract_from_zipfile(eebo_zipfile, extract_files, output_path)

    print(f"Exported {phase2_count} XML files from EEBO-TCP phase 2")

    total_exported = phase1_count + phase2_count
    if total_exported == len(base_ids):
        print(f"Successfully exported all {total_exported} volumes")
    else:
        # unlikely we get here, if there's an error the script will probably crash,
        # but report anyway just in case
        print(f"Only exported {total_exported} volumes, something went wrong...")


def get_marc_ids(eebo_path: Path, base_ids: list) -> dict[str, str]:
    # setup requires EEBO-TCP id mapping file in eebo data dir
    idmapfile = eebo_path / "IDmap.eebo_2015.xml"
    idmapxml = objectify.parse(idmapfile)

    # convert list of ids to a set for fast lookup
    tcp_ids = set(base_ids)
    # construct a dictionary mapping of MARC ESTC ids to extract
    # and their corresponding TCP id
    idmapping = {}
    for tcpitem in idmapxml.findall("TCPitem"):
        # NOTE: some ids are missing ESTC tag but doesn't come up in our set
        if tcpitem.tcpID in tcp_ids:
            # the ID that matches our records is in the BIBNO element, e.g.
            # <BIBNO T="oclc">12226320</BIBNO>
            # convert to string for comparison with marcreader id
            idmapping[str(tcpitem.BIBNO)] = tcpitem.tcpID

    print(f"Found {len(idmapping)} ESTC ids for {len(base_ids)} TCP ids")
    return idmapping


def extract_marc_files(eebo_path: Path, base_ids: list, output_path: Path):
    # get mapping from TCP id to marc ESTC id
    idmap = get_marc_ids(eebo_path, base_ids)

    extracted = 0
    expected = len(idmap)
    marcfile_path = eebo_path / "eebo.mrc"
    with marcfile_path.open("rb") as marcfile:
        reader = pymarc.MARCReader(marcfile, to_unicode=True, utf8_handling="replace")
        # iterate through all records to find the ones we care about (this is slow)
        read_records = 0
        for record in reader:
            read_records += 1
            # ESTC id is 001 identifier
            estc_id = record["001"].value().strip()
            # if this is an id we care about, extract
            if estc_id in idmap:
                # use tcp id for output filename
                # create individual binary marc file with TCP id
                marc_output = output_path / f"{idmap[estc_id]}.mrc"
                record.force_utf8 = True
                marc_output.open("wb").write(record.as_marc())
                extracted += 1
                # stop iterating once we've found all the records we want,
                # saves us from reading ~1k records for our set
                if extracted == expected:
                    break

    print(f"Extracted {extracted} MARC records")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract EEBO-TCP P4 XML files from zip files"
    )
    parser.add_argument(
        "input", help="CSV file with EEBO IDs to select as column 'Volume ID'"
    )
    parser.add_argument(
        "eebo_dir", help="Directory where EEBO-TCP content has been extracted"
    )
    parser.add_argument(
        "output_dir", help="Directory where the selected files should be saved"
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

    # convert directory args to path objects since needed for both steps
    eebo_path = Path(args.eebo_dir)
    output_path = Path(args.output_dir)

    extract_xml_files(eebo_path, base_ids, output_path)
    extract_marc_files(eebo_path, base_ids, output_path)
