"""
One-time script to get ECCO-TCP XML files from the Oxford Text Archive
for the subset of PPA ECCO works that are available in TCP.

XML files are downloaded based on a spreadsheet that provides the Gale/ECCO
identifiers used in PPA with the Gale API.

Overlapping PPA/ECCO-TCP XML documents have already been retrieved and 
this script is not intended to be re-run; it is provided here to document
the process used to gather the materials.
"""


import csv
import pathlib

import requests
from bs4 import BeautifulSoup


def ota_search_by_id(stc_id):
    # https://ota.bodleian.ox.ac.uk/repository/xmlui/discover?query=&filtertype_1=stc_identifier&filter_relational_operator_1=contains&filter_1=&filtertype_2=stc_identifier&filter_relational_operator_2=contains&filter_2=ESTCT64481&filtertype_3=title&filter_relational_operator_3=contains&filter_3=&submit_apply_filter=Apply&query=

    # https://ota.bodleian.ox.ac.uk/repository/xmlui/discover?query=ESTCT64481&submit=Search&filtertype_1=ota_collection&filter_relational_operator_1=equals&filter_1=ECCO-TCP+%28Phase+1%29&filtertype_3=title&filter_relational_operator_3=contains&filter_3=&query=ESTCT64481
    params = {
        # search by ETSC id, limit to ecco-tcp collection
        "query": f"ESTC{stc_id}",
        "filtertype_1": "ota_collection",
        "filter_relational_operator_1": "equals",
        "filter_1": "ECCO-TCP (Phase 1)",
        # "filtertype_1": "stc_identifier",
        # "filter_relational_operator_1": "contains",
        # "filter_1": f"ESTC{stc_id}",
        # limit to ECCO-TCP
        # "filtertype": "ota_collection",
        # "filter_relational_operator": "equals",
        # "filter": "ECCO-TCP+%28Phase+1%29",
    }
    resp = requests.get(
        "https://ota.bodleian.ox.ac.uk/repository/xmlui/discover", params=params
    )
    soup = BeautifulSoup(resp.content, "html.parser")
    item_urls = [
        title.a["href"] for title in soup.find_all("div", class_="artifact-title")
    ]
    return item_urls


def vol_from_url(url):
    return int(url.rsplit(".")[-1])


def get_item_xml(url, output_path):
    # item url looks like this:
    # /repository/xmlui/handle/20.500.12024/K055619.002
    # xml url looks like this:
    # https://ota.bodleian.ox.ac.uk/repository/xmlui/bitstream/handle/20.500.12024/K055619.001/K055619.001.xml?sequence=6&isAllowed=y
    url = url.replace("xmlui/handle", "xmlui/bitstream/handle")
    item_id = url.rsplit("/")[-1]
    xml_url = f"https://ota.bodleian.ox.ac.uk{url}/{item_id}.xml"
    resp = requests.get(xml_url, params={"sequence": 6, "isAllowed": "y"}, stream=True)
    with output_path.open("wb") as fd:
        for chunk in resp.iter_content(chunk_size=1028):
            fd.write(chunk)


if __name__ == "__main__":
    output_path = pathlib.Path("data/ecco-tcp")
    output_path.mkdir(exist_ok=True)

    multivols = {}

    with open("ecco-tcp_overlap.csv") as infile:
        csvreader = csv.DictReader(infile)
        for i, row in enumerate(csvreader):
            item_id = row["source_id"]
            xml_output = output_path / f"{item_id}.xml"
            # skip if already downloaded
            if xml_output.exists():
                continue

            print(f"Looking for {item_id} - {row['record_id']} vol {row['enumcron']}")
            # check if we already have this id
            if item_id in multivols:
                item_url = multivols[item_id][int(row["enumcron"])]
            else:
                # when there are multiple volumes, the search result
                # returns multiple item urls
                item_urls = ota_search_by_id(row["record_id"])
                # if multiple, find by volume and save the rest
                if len(item_urls) > 1:
                    print(f"... found {len(item_urls)} results")
                    if not row["enumcron"]:
                        print("but item does not have a volume")
                        # NOTE: one volume could not be identified by volume;
                        # this one was downloaded manually

                        # skip to next
                        continue

                    by_vol = {vol_from_url(url): url for url in item_urls}
                    item_url = by_vol[int(row["enumcron"])]
                    # if multiple, store in the dict for other rows
                    multivols[row["record_id"]] = by_vol
                else:
                    item_url = item_urls[0]

            get_item_xml(item_url, xml_output)
