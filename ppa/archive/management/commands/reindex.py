from django.core.management.base import BaseCommand
import progressbar

from ppa.archive.models import DigitizedWork
from ppa.archive.solr import get_solr_connection


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

    def add_arguments(self, parser):
        parser.add_argument(
            'source_ids', nargs='*',
            help='Optional list of specific works to index by source (HathiTrust) id.')
        parser.add_argument(
            '-p', '--progress', action='store_true',
            help='Display a progress bar to track the status of the reindex.')

    def handle(self, *args, **kwargs):
        solr, solr_collection = get_solr_connection()
        self.verbosity = kwargs.get('verbosity', self.v_normal)
        self.options = kwargs

        # self.stats = defaultdict(int)
        works = DigitizedWork.objects.all()

        if self.options['source_ids']:
            works = works.filter(source_id__in=self.options['source_ids'])
            # self.stats['total'] = len(ids_to_index)

        # initialize progressbar if requested and indexing more than 5 items
        if self.options['progress'] and works.count() > 5:
            progbar = progressbar.ProgressBar(redirect_stdout=True,
                                              max_value=works.count())
        else:
            progbar = None

        for i, work in enumerate(works):
            solr.index(solr_collection, [work.index_data()])
            if progbar:
                progbar.update(i)
