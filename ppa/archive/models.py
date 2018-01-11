from django.db import models
from django.urls import reverse

from ppa.archive.solr import get_solr_connection


class Collection(models.Model):
    '''A collection of :class:~ppa.archive.models.DigitizedWork instances.'''
    #: the name of the collection
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        '''Override method so that on save, any associated
        works have their names updated.'''
        # Note: This is a potentially expensive operation,
        # but collection shouldn't change often.
        super(Collection, self).save(*args, **kwargs)
        digworks = self.digitizedwork_set.all()
        for work in digworks:
            work.index()


class DigitizedWork(models.Model):
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

    def index(self, commit=False):
        '''Index a :class:~ppa.archive.models.DigitizedWork
        and allow optional commit to ensure results are available.
        '''

        solr, solr_collection = get_solr_connection()
        solr.index(solr_collection, [self.index_data()])

        if commit:
            # force method to hold until old cache is invalidated
            # so that results show using openSearcher and waitSearcher
            solr.commit(solr_collection, openSearcher=True, waitSearcher=True)


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
