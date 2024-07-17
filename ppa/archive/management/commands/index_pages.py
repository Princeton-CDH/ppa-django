"""
Custom multiprocessing Solr index script for page index data.
"""

import queue
from time import sleep

import progressbar
from django.core.management.base import BaseCommand
from django.db import models
from django.template.defaultfilters import pluralize
from parasolr.django import SolrClient, SolrQuerySet
from multiprocess import Process, Queue, cpu_count

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
            page_data = list(Page.page_index_data(digwork))
            page_data_q.put(page_data)

        # by default, signals propagate to all processes;
        # take advantage of that to stop gracefully
        except KeyboardInterrupt:
            # if we get a ctrl-c / keyboard interrupt, stop processing
            # even though queue is not empty
            return

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
            index_data = index_data_q.get(timeout=1)
            solr.update.index(index_data)
            # increase count based on the number of items in the list
            count += len(index_data)
            progbar.update(count)

        # by default, signals propagate to all processes;
        # take advantage of that to stop gracefully
        except KeyboardInterrupt:
            # if we get a ctrl-c / keyboard interrupt, stop adding
            # works to queue even though not all indexing will be finished
            print("KeyboardInterrupt, exiting indexing queue")
            return

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
    sources = {name: code for code, name in DigitizedWork.SOURCE_CHOICES}

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
            "--source", help="Limit to one source", choices=Command.sources.keys()
        )
        parser.add_argument(
            "--expedite",
            help="Only index works with page count mismatch between Solr and database",
            action="store_true",
            default=False,
        )

    def handle(self, *args, **kwargs):
        self.verbosity = kwargs.get("verbosity", self.v_normal)
        num_processes = kwargs.get("processes", cpu_count())
        work_q = Queue()
        page_data_q = Queue()
        # populate the work queue with digitized works that have
        # page content to be indexed
        source_ids = kwargs.get("source_ids", [])

        # unless specific ids are specified, get all works for indexing
        if not source_ids:
            digiworks = DigitizedWork.items_to_index()

            # if single-source indexing is specified, filter items by source
            source = kwargs.get("source")
            if source:
                digiworks = digiworks.filter(source=self.sources[source])
                # calculate total pages to index for single source
                num_pages = Page.total_to_index(source=self.sources[source])
            else:
                num_pages = Page.total_to_index()
        else:
            digiworks = DigitizedWork.objects.filter(source_id__in=source_ids)

            digwork_pages = digiworks.aggregate(page_count=models.Sum("page_count"))
            num_pages = digwork_pages["page_count"]

        # if only indexing specific items by id, don't start more indexing processes
        # than there are records to index
        if source_ids:
            num_processes = min(num_processes, len(source_ids))
        if self.verbosity >= self.v_normal:
            self.stdout.write(
                f"Indexing with {num_processes} process{pluralize(num_processes, 'es')}"
            )

        # if reindexing everything, check db totals against solr
        if not source_ids and self.verbosity >= self.v_normal:
            # check totals; filter by source if specified
            solr_count = self.get_solr_totals(source=kwargs.get("source"))

            work_diff = digiworks.count() - solr_count.get("work", 0)
            page_diff = num_pages - solr_count.get("page", 0)

            if self.verbosity >= self.v_normal:
                if work_diff:
                    # negative = more works in solr than database
                    if work_diff < 0:
                        self.stdout.write(
                            self.style.WARNING(
                                f"{abs(work_diff):,} extra works indexed in Solr; "
                                + " may need to clear old data"
                            )
                        )
                    else:
                        self.stdout.write(f"{work_diff:,} works not indexed in Solr")
                if page_diff:
                    # negative = more pages in solr than expected
                    if page_diff < 0:
                        self.stdout.write(
                            self.style.WARNING(
                                f"{abs(page_diff):,} more pages indexed in Solr than expected"
                            )
                        )

                    else:
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
                # it indicates an error, but page count could be null;
                # if so, assume page count mismatch
                if digwork.page_count is None:
                    # add to list of works to index
                    mismatches.append(digwork)
                    # warn about the missing page count
                    if self.verbosity >= self.v_normal:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Warning: {digwork} page count is not set in database"
                            )
                        )

                elif digwork.page_count != solr_page_count:
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
        data_feeders = []
        for i in range(max(1, kwargs["processes"] - 1)):
            process = Process(target=page_index_data, args=(work_q, page_data_q))
            process.start()
            data_feeders.append(process)

        # give the page data a head start, since indexing is faster
        sleep(1)

        # start a single indexing process
        indexer = Process(
            target=process_index_queue,
            args=(page_data_q, num_pages, work_q),
        )
        indexer.start()
        try:
            # block until indexer has completed, but catch keyboard interrupt
            indexer.join()
        except KeyboardInterrupt:
            # if user interrupts indexing with Ctrl-C,
            # terminate and join all the processes
            indexer.terminate()
            indexer.join()
            for proc in data_feeders:
                proc.terminate()
                proc.join()

            work_q.close()
            work_q.cancel_join_thread()
            page_data_q.close()
            page_data_q.cancel_join_thread()

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
        return

    def get_solr_totals(self, source=None):
        # query for all items and facet by item type to get work/page counts
        solr_items = SolrQuerySet().all().facet("item_type")

        # filter by source when specified
        if source is not None:
            # source is present on works but not pages;
            # use a join query to filter on pages associated with works by source
            source_filter = f'source_t:"{source}"'
            solr_items = solr_items.search(
                f"{source_filter} OR {{!join from=id to=group_id_s}}{source_filter}"
            )

        facets = solr_items.get_facets()
        # facet returns an ordered dict
        if facets and facets.facet_fields:
            return facets.facet_fields.get("item_type", {})

        # if facets or facet_fields not set, count for all types is zero
        return {}
