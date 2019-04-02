'''

Utility code related to :mod:`ppa.archives`

'''

from collections import OrderedDict
from json.decoder import JSONDecodeError

from ppa.archive import hathi
from ppa.archive.models import DigitizedWork
from ppa.archive.signals import IndexableSignalHandler
from ppa.archive.solr import get_solr_connection


class HathiImporter:
    '''Logic for creating new :class:`~ppa.archive.models.DigitizedWork`
    records from HathiTrust. For use in views and manage commands.'''

    existing_ids = None

    #: status - successfully imported record
    SUCCESS = 1
    #: status - skipped because already in the database
    SKIPPED = 2

    #: human-readable message to display for result status
    status_message = {
        SUCCESS: 'Success',
        SKIPPED: 'Skipped; already in the database',
        hathi.HathiItemNotFound: 'Error loading record; check that id is valid.',
        hathi.HathiItemForbidden: 'Permission denied to download data.',
        # only saw this one on day, but this was what it was
        JSONDecodeError: 'HathiTrust catalog temporarily unavailable (malformed response).'
    }

    def __init__(self, htids):
        self.imported_works = []
        self.results = {}
        self.htids = htids
        # initialize a bibliographic api client to use the same
        # session when adding multiple items
        self.bib_api = hathi.HathiBibliographicAPI()

        # not calling filter_existing_ids here because it is
        # probably not desirable behavior for current hathi_import script

    def filter_existing_ids(self):
        '''Check for any ids that are in the database so they can
        be skipped for import.  Populates :attr:`existing_ids`
        with an :class:`~collections.OrderedDict` of htid -> id for
        ids already in the database and filters :attr:`htids`.

        :param htids: list of HathiTrust Identifiers (correspending to
            :attr:`~ppa.archive.models.DigitizedWork.source_id`)
        '''
        # query for digitized work with these ids and return
        # source id, db id and generate an ordered dict
        self.existing_ids = OrderedDict(
            DigitizedWork.objects.filter(source_id__in=self.htids) \
                                 .values_list('source_id', 'id'))

        # create initial results dict, marking any skipped ids
        self.results = OrderedDict(
            (htid, self.SKIPPED)
            for htid in self.existing_ids.keys())

        # filter to ids that are not already present in the database
        self.htids = set(self.htids) - set(self.existing_ids.keys())

    def add_items(self, log_msg_src=None, user=None):
        '''Add new items from HathiTrust.

        :params log_msg_src: optional source of change to be included in
            log entry message

        '''
        # disconnect indexing signal handler before adding new content
        IndexableSignalHandler.disconnect()

        for htid in self.htids:
            try:
                digwork = DigitizedWork.add_from_hathi(
                    htid, self.bib_api, get_data=True,
                    log_msg_src=log_msg_src, user=user)
                if digwork:
                    self.imported_works.append(digwork)

                self.results[htid] = self.SUCCESS
            except (hathi.HathiItemNotFound, JSONDecodeError,
                    hathi.HathiItemForbidden) as err:
                # json decode error occurred 3/26/2019 - catalog was broken
                # and gave a 200 Ok response with PHP error content
                # hopefully temporary, but could occur again...

                # store the actual error as the results, so that
                # downstream code can report as desired
                self.results[htid] = err

                # remove the partial record if one was created
                # (i.e. if metadata succeeded but data failed)
                DigitizedWork.objects.filter(source_id=htid).delete()

        # reconnect indexing signal handler
        IndexableSignalHandler.connect()

    def index(self):
        '''Index newly imported content, both metadata and full text.'''
        if self.imported_works:
            DigitizedWork.index_items(self.imported_works)
            for work in self.imported_works:
                # index page index data in chunks (returns a generator)
                DigitizedWork.index_items(work.page_index_data())

            solr, solr_collection = get_solr_connection()
            solr.commit(solr_collection, openSearcher=True)

    def get_status_message(self, status):
        '''Get a readable status message for a given status'''
        try:
            # try message for simple states (success, skipped)
            return self.status_message[status]
        except KeyError:
            # if that fails, check for error message
            return self.status_message[status.__class__]

    def output_results(self):
        '''Provide human-readable report of results for each
        id that was processed.'''
        return OrderedDict([
            (htid, self.get_status_message(status))
            for htid, status in self.results.items()
        ])
