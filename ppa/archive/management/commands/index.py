'''
**index** is a custom manage command to index PPA digitized work and page
content into Solr.  It should be run *after* content has been imported
to the project database via the **hathi_import** manage command.

Page content will be indexed from a local copy of dataset files under the
configured **HATHI_DATA** path in pairtree format retrieved by rsync.
(Note that pairtree data must include pairtree version file to be valid.)

By default, indexes _all_ content, both digitized works and pages.  You
can optionally specify works or pages only, or index specific items
by hathi id. If you request a specific id, it must exist in the database
and the pairtree content for the items still must exist at the configured path.

A progress bar will be displayed by default if there are more than 5
items to process.  This can be suppressed via script options.

Example usage::

    # index everything
    python manage.py index
    # index specific items
    python manage.py index htid1 htid2 htid3
    # index works only (skip pages)
    python manage.py index -i works
    # index pages only (skip works)
    python manage.py index -i pages
    # suppress progressbar
    python manage.py index --no-progress

'''


import itertools

from django.core.management.base import BaseCommand, CommandError
from django.core.paginator import Paginator
from django.db.models import Sum
import progressbar
# from urllib3.exceptions import HTTPError
from SolrClient.exceptions import ConnectionError
from requests.exceptions import RequestException

from ppa.archive.models import DigitizedWork
from ppa.archive.solr import get_solr_connection, Indexable


class Command(BaseCommand):
    '''Reindex digitized items into Solr that have already been imported'''
    help = __doc__

    solr = None
    solr_collection = None
    bib_api = None
    hathi_pairtree = {}
    stats = None

    options = {}
    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    #: solr params for index call; currently set to commit within 5 seconds
    solr_index_opts = {"commitWithin": 5000}
    # NOTE: not sure what is reasonable here, but without some kind of commit,
    # Solr seems to quickly run out of memory

    def add_arguments(self, parser):
        parser.add_argument(
            'source_ids', nargs='*',
            help='Optional list of specific works to index by source (HathiTrust) id.')
        parser.add_argument(
            '-i', '--index', choices=['all', 'works', 'pages'], default='all',
            help='Index only works or pages (by default indexes all)')
        parser.add_argument(
            '--no-progress', action='store_true',
            help='Do not display progress bar to track the status of the reindex.')

    def handle(self, *args, **kwargs):
        self.solr, self.solr_collection = get_solr_connection()
        self.verbosity = kwargs.get('verbosity', self.v_normal)
        self.options = kwargs

        # self.stats = defaultdict(int)
        works = DigitizedWork.objects.all()

        if self.options['source_ids']:
            works = works.filter(source_id__in=self.options['source_ids'])

        total_to_index = 0
        # calculate total to index based on what we are indexing
        if self.options['index'] in ['works', 'all']:
            # total works to be indexed
            total_to_index += works.count()
        if self.options['index'] in ['pages', 'all']:
            # total pages to be indexed
            # NOTE: should always be a value if id is valid, but fallback to zero for None
            total_to_index += works.aggregate(total_pages=Sum('page_count'))['total_pages'] or 0

        # initialize progressbar if requested and indexing more than 5 items
        progbar = None
        if not self.options['no_progress'] and total_to_index > 5:
            progbar = progressbar.ProgressBar(redirect_stdout=True,
                                              max_value=total_to_index)

        count = 0

        # index works
        if self.options['index'] in ['works', 'all']:
            # index in chunks and update progress bar
            count = self.index(works, progbar=progbar)

        self.solr.commit(self.solr_collection)

        # index pages for each work
        if self.options['index'] in ['pages', 'all']:
            for work in works:
                # index page index data in chunks (returns a generator)
                self.index(work.page_index_data())

                # for simplicity, update progress bar for each work
                # rather than each chunk of pages
                count += work.page_count
                if progbar:
                    progbar.update(count)

        self.solr.commit(self.solr_collection)

    def index(self, index_data, progbar=None):
        '''index an iterable into the configured solr instance
        and solr collection'''

        # NOTE: currently no good way to catch a connection
        # error when Solr is not running because we get multiple
        # connections during handling of exceptions.
        try:
            # index in chunks and update progress bar if there is one
            return Indexable.index_items(index_data, progbar=progbar)
        except Exception as err:
        # except (ConnectionError, RequestException) as err:
            # NOTE: this is still pretty ugly; what part should we return?
            raise CommandError(err)
