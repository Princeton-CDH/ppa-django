from io import BytesIO

from django.db import models
from django.urls import reverse
from mezzanine.core.fields import RichTextField

from ppa.archive.hathi import HathiBibliographicAPI
from ppa.archive.solr import get_solr_connection



class Collection(models.Model):
    '''A collection of :class:`ppa.archive.models.DigitizedWork` instances.'''
    #: the name of the collection
    name = models.CharField(max_length=255)
    #: a RichText description of the collection
    description = RichTextField(blank=True)

    def __str__(self):
        return self.name

    def full_index(self, params=None):
        '''Index or reindex a collection's associated works.'''
        # guard against this being called on an unsaved instance
        if not self.pk:
            raise ValueError(
                'Collection instance needs to have a primary key value before '
                'this method is called.'
            )
        solr, solr_collection = get_solr_connection()
        digworks = self.digitizedwork_set.all()
        solr_docs = [work.index_data() for work in digworks]
        # adapted from hathi import logic
        solr.index(solr_collection, solr_docs,
            params=params)

    def save(self, *args, **kwargs):
        '''Override method so that on save, any associated
        works have their names updated if collection name has changed.'''
        # first handle cases where this is a new save, just save and return
        if not self.pk:
            super(Collection, self).save(*args, **kwargs)
            return
        # if it has been saved, get the original
        orig = Collection.objects.get(pk=self.pk)
        if orig.name != self.name:
            # update object with new name
            super(Collection, self).save(*args, **kwargs)
            # reindex its works and commit the result
            self.full_index()
        # saved but no name change, so just save
        else:
            super(Collection, self).save(*args, **kwargs)


class DigitizedWork(models.Model):
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
    # using char for now in case not all numeric
    pub_date = models.CharField('Publication Date', max_length=255, blank=True)
    #: number of pages in the work
    page_count = models.PositiveIntegerField(null=True, blank=True)
    #: collections that this work is part of
    collections = models.ManyToManyField(Collection, blank=True)
    #: date added to the archive
    added = models.DateTimeField(auto_now_add=True)
    #: date of last modification of the local record
    updated = models.DateTimeField(auto_now=True)

    def get_absolute_url(self):
        '''
        Return object's url for
        :class:`ppa.archive.views.DigitizedWorkDetailView`
        '''
        return reverse('archive:detail', kwargs={'source_id': self.source_id})

    def __str__(self):
        '''Default string display. Uses :attr:`source_id`'''
        return self.source_id

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

    def index(self, params=None):
        '''Index a :class:`ppa.archive.models.DigitizedWork`
        and allow optional commit to ensure results are available.
        '''

        solr, solr_collection = get_solr_connection()
        solr.index(solr_collection, [self.index_data()], params=params)

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
            'collections': [collection.name for collection
                            in self.collections.all()],
            # hard-coded to distinguish from & sort with pages
            'item_type': 'work',
            'order': '0',
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
