"""
Custom multiprocessing Solr index script for page index data.
"""

import queue
from multiprocess import Process, Queue, cpu_count
from time import sleep

import progressbar
from django.core.management.base import BaseCommand
from parasolr.django import SolrClient, SolrQuerySet

from ppa.archive.models import DigitizedWork, Page
from ppa.archive.solr import PageSearchQuerySet


def page_index_data(work_q, page_data_q):
    """Function to generate page index data and add it to
    a queue. Takes a queue with digitized works to generate pages
    for and a queue where page data will be added."""
    while True:
        try:
            # convert the generator to a list
            digwork = work_q.get(timeout=1)
            # — might be nice to chunk, but most books are small
            # enough it doesn't matter that much
            page_data_q.put(list(Page.page_index_data(digwork)))
        except queue.Empty:
            # worker is done when the work queue is empty
            return


def process_index_queue(index_data_q, total_to_index, work_q):
    """Function to send index data to Solr. Takes a
    queue to poll for index data, a total of the items
    to be indexed (for use with progess bar), and a work queue
    as a way of checking that all indexing is complete."""

    solr = SolrClient()
    progbar = progressbar.ProgressBar(
        redirect_stdout=True, max_value=total_to_index, max_error=False
    )
    count = 0
    while True:
        try:
            # get data from the queue and put it into Solr
            # block with a timeout
            index_data = index_data_q.get(timeout=5)
            solr.update.index(index_data)
            # increase count based on the number of items in the list
            count += len(index_data)
            progbar.update(count)
        except queue.Empty:
            # only end if work q is also empty; otherwise, loop again
            # indexer has just gotten ahead of page index data
            if work_q.empty():
                progbar.finish()
                # finish indexing process
                return


class Command(BaseCommand):
    """Index page data in Solr (multiprocessor implementation)"""

    help = __doc__

    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    def add_arguments(self, parser):
        parser.add_argument(
            "-p",
            "--processes",
            default=cpu_count(),
            type=int,
            help="Number of processes to use " + "(cpu_count by default: %(default)s)",
        )
        parser.add_argument(
            "source_ids", nargs="*", help="List of specific items to index (optional)"
        )
        parser.add_argument(
            "--expedite",
            help="Only index works with page count mismatch between Solr and database",
            action="store_true",
            default=False,
        )

    def handle(self, *args, **kwargs):
        self.verbosity = kwargs.get("verbosity", self.v_normal)
        if self.verbosity >= self.v_normal:
            self.stdout.write(
                "Indexing with %d processes" % max(2, kwargs["processes"])
            )
        work_q = Queue()
        page_data_q = Queue()
        # populate the work queue with digitized works that have
        # page content to be indexed
        source_ids = kwargs.get("source_ids", [])

        if not source_ids:
            digiworks = DigitizedWork.items_to_index()
            num_pages = Page.total_to_index()
        else:
            digiworks = DigitizedWork.objects.filter(source_id__in=source_ids)
            num_pages = sum([dw.page_count for dw in digiworks])

        # if reindexing everything, check db totals against solr
        if not source_ids and self.verbosity >= self.v_normal:
            # check totals
            solr_count = self.get_solr_totals()

            work_diff = digiworks.count() - solr_count.get("work", 0)
            page_diff = num_pages - solr_count.get("page", 0)

            if self.verbosity >= self.v_normal:
                if work_diff:
                    self.stdout.write(f"{work_diff:,} works not indexed in Solr")
                if page_diff:
                    self.stdout.write(f"{page_diff:,} pages not indexed in Solr")

        if kwargs.get("expedite"):
            # find works with missing pages
            facets = (
                PageSearchQuerySet()
                .filter(item_type="page")
                .facet("group_id", limit=-1)
                .get_facets()
            )
            mismatches = []
            pages_per_work = facets.facet_fields["group_id"]
            for digwork in DigitizedWork.items_to_index():
                solr_page_count = pages_per_work.get(digwork.index_id(), 0)
                if digwork.page_count != solr_page_count:
                    # add to list of works to index
                    mismatches.append(digwork)

                    # in verbose mode, report details
                    if self.verbosity > self.v_normal:
                        diff_msg = ""
                        if digwork.page_count > solr_page_count:
                            diff_msg = f"missing {digwork.page_count - solr_page_count}"
                        else:
                            diff_msg = f"extra {solr_page_count - digwork.page_count}"

                        self.stdout.write(
                            f"{digwork} : {diff_msg} "
                            + f"(db: {digwork.page_count}, solr: {solr_page_count})"
                        )

            if self.verbosity >= self.v_normal:
                self.stdout.write(
                    f"Indexing pages for {len(mismatches)} works with page count mismatches"
                )
            # only index works with page count mismatches
            digiworks = mismatches

        for digwork in digiworks:
            work_q.put(digwork)

        # start multiple processes to populate the page index data queue
        # (need at least 1 page data process, no matter what was specified)
        for i in range(max(1, kwargs["processes"] - 1)):
            Process(target=page_index_data, args=(work_q, page_data_q)).start()

        # give the page data a head start, since indexing is faster
        sleep(10)
        # start a single indexing process
        indexer = Process(
            target=process_index_queue,
            args=(page_data_q, num_pages, work_q),
        )
        indexer.start()
        # block until indexer has completed
        indexer.join()

        # print a summary of solr totals by item type
        if self.verbosity >= self.v_normal:
            item_totals = []
            for item_type, total in self.get_solr_totals().items():
                item_totals.append(
                    "%d %s%s" % (total, item_type, "" if total == 1 else "s")
                )
            self.stdout.write(
                "\nItems in Solr by item type: %s" % (", ".join(item_totals))
            )

    def get_solr_totals(self):
        facets = SolrQuerySet().all().facet("item_type").get_facets()
        # facet returns an ordered dict
        return facets.facet_fields.item_type
