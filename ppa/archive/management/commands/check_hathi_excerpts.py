import csv

from django.core.management.base import BaseCommand
from pairtree import storage_exceptions

from intspan import intspan

from ppa.archive.models import DigitizedWork
from ppa.archive.templatetags.ppa_tags import hathi_page_url


class Command(BaseCommand):
    """Check page alignment for excerpted HathiTrust digitized items."""

    help = __doc__

    #: normal verbosity level
    v_normal = 1
    #: verbosity level for the current run; defaults to 1 / normal
    verbosity = v_normal

    def handle(self, *args, **kwargs):
        self.verbosity = kwargs.get("verbosity", self.verbosity)

        # find all excerpted, non-suppressed hathi volumes
        hathi_vols = DigitizedWork.objects.filter(
            source=DigitizedWork.HATHI,
            status=DigitizedWork.PUBLIC,
        ).exclude(item_type=DigitizedWork.FULL)

        output_fields = [
            "source_id",
            "unique_id",
            "pages_orig",
            "pages_digital",
            "orig_label_match",
            "pages_digital_corrected",
            "old_hathi_start",
            "new_hathi_start",
            "notes",
        ]

        with open("ppa-excerpt-pagecheck.csv", "w") as csvfile:
            csvwriter = csv.DictWriter(csvfile, fieldnames=output_fields)
            csvwriter.writeheader()

            for digwork in hathi_vols:
                info = {
                    "source_id": digwork.source_id,
                    # source id + first page (currently digital, will be switching to original)
                    "unique_id": digwork.index_id(),
                    "pages_orig": digwork.pages_orig,
                    "pages_digital": digwork.pages_digital,
                    "old_hathi_start": hathi_page_url(
                        digwork.source_id, digwork.first_page_digital()
                    ),
                }
                # NOTE: mets loading copied from hathi_page_index_data method
                # worth movint to a method on the hathi object?
                try:
                    mmets = digwork.hathi.mets_xml()
                except storage_exceptions.ObjectNotFoundException:
                    # document the error in the output csv, stop processing
                    info["notes"] = "pairtree data not found"
                    csvwriter.writerow(info)
                    continue
                except storage_exceptions.PartNotFoundException:
                    info["notes"] = "error loading mets file (part not found)"
                    csvwriter.writerow(info)
                    continue

                # make a list of page labels and order from mets structmap
                page_info = [
                    {"order": page.order, "label": page.orderlabel}
                    # also have access to label (@LABEL vs @ORDERLABEL)
                    for page in mmets.structmap_pages
                ]

                # use digital page range to get the first page in the mets
                # that would be included with current digital range (1-based index)
                try:
                    excerpt_first_page = page_info[digwork.first_page_digital() + 1]
                except IndexError:
                    if digwork.first_page_digital() >= len(page_info):
                        excerpt_first_page[-1]
                        info["notes"] = "digital page out of range; trying last page"

                # some mets records don't have labels
                # or, label attribute may be present but empty
                # do we need to check if all pages are missing labels?
                if (
                    excerpt_first_page["label"] is None
                    or excerpt_first_page["label"].strip() == ""
                ):
                    # add a note that mets doesn't have labels, stop processing
                    info["notes"] = "no page label in METS structmap"
                    csvwriter.writerow(info)
                    continue

                # check if METS page label for the first page in range
                # matches the desired first original page
                if excerpt_first_page["label"] != str(digwork.first_page_original()):
                    info["orig_label_match"] = "N"
                    # if they don't match, can we calculate the offset?
                    # (only works for numeric page labels)
                    try:
                        diff = int(digwork.first_page_original()) - int(
                            excerpt_first_page["label"]
                        )
                        # calculate the expected new digital page range
                        # - apply the difference to each number in range,
                        #   since we do have some discontinuous ranges
                        # - convert back to intspan so we can output in
                        #   page range format (1-3 or 1-3,5)
                        new_range = [n + diff for n in digwork.page_span]
                        info["pages_digital_corrected"] = intspan(new_range)
                        info["new_hathi_start"] = hathi_page_url(
                            digwork.source_id, new_range[0]
                        )
                    except ValueError as err:
                        info["notes"] = "could not calculate page offset (%s)" % err

                else:
                    info["orig_label_match"] = "Y"
                    info["notes"] = "page labels match"

                # either way, write out the info
                csvwriter.writerow(info)
