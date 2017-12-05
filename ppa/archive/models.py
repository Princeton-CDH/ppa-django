from django.db import models

# Create your models here.

class DigitizedWork(models.Model):
    # stub record to manage digitized works included in PPA
    # basic metadata
    # - title, author, place of publication, date
    # added, updated
    # original id / url?
    #: source identifier; hathi id for HathiTrust materials
    source_id = models.CharField(max_length=255, unique=True)
    #: title of the work; using TextField to allow for long titles
    title = models.TextField()
    #: enumeration/chronology
    enumcron = models.CharField('Enumeration/Chronology', max_length=255,
        null=True)
        # TODO: what is the generic/non-hathi name for this? volume/version?

    # TODO: foreign key for author?
    author = models.CharField(max_length=255)
    #: place of publication
    pub_place = models.CharField('Place of Publication', max_length=255)
    #: publisher
    publisher = models.CharField(max_length=255)
    # using char for now in case not all numeric
    pub_date = models.CharField('Publication Date', max_length=255)
    #: number of pages in the work
    page_count = models.PositiveIntegerField(null=True, blank=True)
    #: date added to the archive
    added = models.DateTimeField(auto_now_add=True)
    #: date of last modification of the local record
    updated = models.DateTimeField(auto_now=True)

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
        # hathi version/volume information for this specificy copy of a work
        self.enumcron = copy_details['enumcron'] or ''
        # set fields from marc if available
        if bibdata.marcxml:
            self.author = bibdata.marcxml.author() or ''
            if '260' in bibdata.marcxml:
                self.pub_place = bibdata.marcxml['260']['a']
                self.publisher = bibdata.marcxml['260']['b']
            # maybe: consider getting volume & series directly from
            # marc rather than relying on hathi enumcron ()

        # should also consider storing:
        # - last update, rights code / rights string, item url
        # (maybe solr only?)

    def index_data(self):
        '''data for indexing in Solr'''
        return {
            'id': self.source_id,
            'htid': self.source_id,
            'item_type': 'work',
            'title': self.title,
            'pub_date': self.pub_date,
            'pub_place': self.pub_place,
            'publisher': self.publisher,
            'enumcron': self.enumcron,
            'author': self.author
        }






