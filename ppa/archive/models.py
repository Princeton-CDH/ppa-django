import logging
import os.path
from zipfile import ZipFile

from cached_property import cached_property
from django.conf import settings
from django.db import models
from django.urls import reverse
from mezzanine.core.fields import RichTextField
from pairtree import pairtree_path, pairtree_client

from ppa.archive.hathi import HathiBibliographicAPI
from ppa.archive.solr import Indexable


logger = logging.getLogger(__name__)


class Collection(models.Model):
    '''A collection of :class:`ppa.archive.models.DigitizedWork` instances.'''
    #: the name of the collection
    name = models.CharField(max_length=255)
    #: a RichText description of the collection
    description = RichTextField(blank=True)

    def __str__(self):
        return self.name

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # store a copy of model data to allow for checking if
        # it has changed
        self.__initial = self.__dict__.copy()

    def save(self, *args, **kwargs):
        """
        Saves model and set initial state.
        """
        super().save(*args, **kwargs)
        # update copy of initial data to reflect saved state
        self.__initial = self.__dict__.copy()

    @property
    def name_changed(self):
        '''check if name has been changed (only works on current instance)'''
        return self.name != self.__initial['name']


class DigitizedWork(models.Model, Indexable):
    '''
    Record to manage digitized works included in PPA and store their basic
    metadata.
    '''
    # stub record to manage digitized works included in PPA
    # basic metadata
    # - title, author, place of publication, date
    # added, updated
    # original id / url?
    #: source identifier; hathi id for HathiTrust materials
    source_id = models.CharField(max_length=255, unique=True)
    #: source url where the original can be accessed
    source_url = models.URLField(max_length=255)
    #: title of the work; using TextField to allow for long titles
    title = models.TextField()
    #: enumeration/chronology (hathi-specific)
    enumcron = models.CharField('Enumeration/Chronology', max_length=255,
                                blank=True)
    # TODO: what is the generic/non-hathi name for this? volume/version?

    # NOTE: may eventually to convert to foreign key
    author = models.CharField(max_length=255, blank=True)
    #: place of publication
    pub_place = models.CharField('Place of Publication', max_length=255,
                                 blank=True)
    #: publisher
    publisher = models.TextField(max_length=255, blank=True)
    # Needs to be integer to allow aggregating max/min, filtering by date
    pub_date = models.PositiveIntegerField('Publication Date', null=True, blank=True)
    #: number of pages in the work
    page_count = models.PositiveIntegerField(null=True, blank=True)
    #: public notes field for this work
    notes = models.TextField(blank=True)
    #: collections that this work is part of
    collections = models.ManyToManyField(Collection, blank=True)
    #: date added to the archive
    added = models.DateTimeField(auto_now_add=True)
    #: date of last modification of the local record
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('title',)

    def get_absolute_url(self):
        '''
        Return object's url for
        :class:`ppa.archive.views.DigitizedWorkDetailView`
        '''
        return reverse('archive:detail', kwargs={'source_id': self.source_id})

    def __str__(self):
        '''Default string display. Uses :attr:`source_id`'''
        return self.source_id

    @property
    def srcid(self):
        '''alias for :attr:`source_id` for consistency with solr attributes'''
        # hopefully temporary workaround until solr fields made consistent
        return self.source_id

    @property
    def src_url(self):
        '''alias for :attr:`source_url` for consistency with solr attributes'''
        # hopefully temporary workaround until solr fields made consistent
        return self.source_url

    def populate_from_bibdata(self, bibdata):
        '''Update record fields based on Hathi bibdata information.
        Full record is required in order to set all fields

        :param bibdata: bibliographic data returned from HathiTrust
            as instance of :class:`ppa.archive.hathi.HathiBibliographicRecord`

        '''
        self.title = bibdata.title
        # NOTE: might also want to store sort title
        # pub date returned in api JSOn is list; use first for now (if available)
        if bibdata.pub_dates:
            self.pub_date = bibdata.pub_dates[0]
        copy_details = bibdata.copy_details(self.source_id)
        # hathi version/volume information for this specific copy of a work
        self.enumcron = copy_details['enumcron'] or ''
        # hathi source url can currently be inferred from htid, but is
        # included in the bibdata in case it changes - so let's just store it
        self.source_url = copy_details['itemURL']
        # set fields from marc if available
        if bibdata.marcxml:
            self.author = bibdata.marcxml.author() or ''
            if '260' in bibdata.marcxml:
                self.pub_place = bibdata.marcxml['260']['a'] or ''
                self.publisher = bibdata.marcxml['260']['b'] or ''
            # maybe: consider getting volume & series directly from
            # marc rather than relying on hathi enumcron ()

        # should also consider storing:
        # - last update, rights code / rights string, item url
        # (maybe solr only?)

    def handle_collection_save(sender, instance, **kwargs):
        '''signal handler for collection save; reindex associated digitized works'''
        # only reindex if collection name has changed
        if instance.name_changed:
            # if the collection has any works associated
            works = instance.digitizedwork_set.all()
            if works.exists():
                logger.debug('collection save, reindexing %d related works', works.count())
                Indexable.index_items(works, params={'commitWithin': 3000})

    def handle_collection_delete(sender, instance, **kwargs):
        '''signal handler for collection delete; clear associated digitized
        works and reindex'''
        logger.debug('collection delete')
        # get a list of ids for collected works before clearing them
        digwork_ids = instance.digitizedwork_set.values_list('id', flat=True)
        # find the items based on the list of ids to reindex
        digworks = DigitizedWork.objects.filter(id__in=list(digwork_ids))

        # NOTE: this sends pre/post clear signal, but it's not obvious
        # how to take advantage of that
        instance.digitizedwork_set.clear()
        Indexable.index_items(digworks, params={'commitWithin': 3000})

    index_depends_on = {
        'collections': {
            'save': handle_collection_save,
            'delete': handle_collection_delete,

        }
    }

    def index_id(self):
        '''source id is used as solr identifier'''
        return self.source_id

    def index_data(self):
        '''data for indexing in Solr'''
        return {
            'id': self.source_id,
            'srcid': self.source_id,
            'src_url': self.source_url,
            'title': self.title,
            'pub_date': self.pub_date,
            'pub_place': self.pub_place,
            'publisher': self.publisher,
            'enumcron': self.enumcron,
            'author': self.author,
            'notes': self.notes,
            'collections': [collection.name for collection
                            in self.collections.all()],
            # hard-coded to distinguish from & sort with pages
            'item_type': 'work',
            'order': '0',
        }

    @cached_property
    def hathi_prefix(self):
        '''hathi pairtree prefix (first portion of the source id, short-form
        identifier for owning institution)'''
        return self.source_id.split('.', 1)[0]

    @cached_property
    def hathi_pairtree_id(self):
        '''hathi pairtree identifier (second portion of source id)'''
        return self.source_id.split('.', 1)[1]

    @cached_property
    def hathi_content_dir(self):
        '''hathi content directory for this work (within the corresponding
        pairtree)'''
        # contents are stored in a directory named based on a
        # pairtree encoded version of the id
        return pairtree_path.id_encode(self.hathi_pairtree_id)

    def hathi_pairtree_object(self, ptree_client=None):
        '''get a pairtree object for the current work'''
        if ptree_client is None:
            # get pairtree client if not passed in
            ptree_client = pairtree_client.PairtreeStorageClient(
                self.hathi_prefix,
                os.path.join(settings.HATHI_DATA, self.hathi_prefix))

        # return the pairtree object for current work
        return ptree_client.get_object(self.hathi_pairtree_id,
                                       create_if_doesnt_exist=False)

    def hathi_zipfile_path(self, ptree_client=None):
        '''path to zipfile within the hathi contents for this work'''
        pairtree_obj = self.hathi_pairtree_object(ptree_client=ptree_client)
        # - expect a mets file and a zip file
        # NOTE: not yet making use of the metsfile
        # - don't rely on them being returned in the same order on every machine
        parts = pairtree_obj.list_parts(self.hathi_content_dir)
        # find the first zipfile in the list (should only be one)
        ht_zipfile = [part for part in parts if part.endswith('zip')][0]

        return os.path.join(pairtree_obj.id_to_dirpath(),
                            self.hathi_content_dir, ht_zipfile)

    def page_index_data(self):
        '''Get page content for this work from Hathi pairtree and return
        data to be indexed in solr.'''

        # read zipfile contents in place, without unzipping
        with ZipFile(self.hathi_zipfile_path()) as ht_zip:
            filenames = ht_zip.namelist()

            # yield a generator of index data for each page
            for pagefilename in filenames:
                with ht_zip.open(pagefilename) as pagefile:
                    page_id = os.path.splitext(os.path.basename(pagefilename))[0]
                    yield {
                        'id': '%s.%s' % (self.source_id, page_id),
                        'srcid': self.source_id,   # for grouping with work record
                        'content': pagefile.read().decode('utf-8'),
                        'order': page_id,
                        'item_type': 'page'
                    }

    def get_metadata(self, metadata_format):
        '''Get metadata for this item in the specified format.
        Currently only supports marc.'''

        if metadata_format == 'marc':
            # get metadata from hathi bib api and serialize
            # as binary marc
            bib_api = HathiBibliographicAPI()
            bibdata = bib_api.record('htid', self.source_id)
            return bibdata.marcxml.as_marc()

        # error for unknown
        raise ValueError('Unsupported format %s' % metadata_format)
