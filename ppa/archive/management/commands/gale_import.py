"""
**gale_import** is a custom manage command for bulk import of Gale
materials into the local database for management.


"""

from django.core.management.base import BaseCommand, CommandError
from parasolr.django.signals import IndexableSignalHandler

from ppa.archive.gale import GaleAPI
from ppa.archive.models import DigitizedWork


class Command(BaseCommand):
    '''Import Gale content into PPA for management and search'''
    help = __doc__

    bib_api = None
    hathi_pairtree = {}
    stats = None
    options = {}
    #: normal verbosity level
    v_normal = 1
    verbosity = v_normal

    def add_arguments(self, parser):
        parser.add_argument(
            'ids', nargs='*',
            help='Optional list of specific items to import by Gale id.')
        # parser.add_argument(
        #     '-u', '--update', action='store_true',
        #     help='Update local content even if source record has not changed.')
        # parser.add_argument(
        #     '--progress', action='store_true',
        #     help='Display a progress bar to track the status of the import.')

    def handle(self, *args, **kwargs):
        # disconnect signal handler for on-demand indexing, for efficiency
        # (index in bulk after an update, not one at a time)
        IndexableSignalHandler.disconnect()

        self.gale_api = GaleAPI()

        for gale_id in kwargs['ids']:
            if self.verbosity >= self.v_normal:
                self.stdout.write(gale_id)
            digwork = self.import_digitizedwork(gale_id)

    def import_digitizedwork(self, gale_id):
        """Import a single work into the database.
        Retrieves bibliographic data from Gale API."""

        item_record = self.gale_api.get_item(gale_id)

        # document metadata is under
        doc_metadata = item_record['doc']
        # gale url includes user parameter, but we don't want to keep it
        gale_url = doc_metadata['isShownAt'].split('&u=', 1)[0]

        # create new stub record and populate it from api response
        digwork = DigitizedWork.objects.create(
            source_id=gale_id,  # or doc_metadata['id']; format GALE|CW###
            source=DigitizedWork.GALE,
            source_url=gale_url,
            title=doc_metadata['title'],
            # subtitle='',
            # sort_title='', # marc ?
            # authors is multivalued and not listed lastname first;
            # pull from citation? (if not from marc)
            author=', '.join(doc_metadata['authors']),
            # doc_metadata['publication']    includes title and date
            # pub_place
            # publisher
            # doc_metadata['publication']['date'] but not solely numeric
            # pub_date
            page_count=len(item_record['pageResponse']['pages']),
            notes=doc_metadata['citation']  # store citation in notes for now
        )

        # try:
        #     digwork = DigitizedWork.add_from_hathi(
        #         htid, self.bib_api, update=self.options['update'],
        #         log_msg_src='via hathi_import script')
        # except HathiItemNotFound:
        #     self.stdout.write("Error: Bibliographic data not found for '%s'" % htid)
        #     self.stats['error'] += 1
        #     return

        # TODO: create log entry to document import

        # NOTE: item record includes page metadata; we should index
        # at the same time as import

        return digwork

