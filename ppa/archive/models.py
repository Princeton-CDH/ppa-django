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
    #: title of the work
    title = models.CharField(max_length=255)
    #: enumeration/chronology
    enumcron = models.CharField('Enumeration/Chronology', max_length=255,
        null=True)
        # TODO: what is the generic/non-hathi name for this? volume/version?

    # TODO: foreign key for author?
    author = models.CharField(max_length=255)
    pub_place = models.CharField('Place of Publication', max_length=255)
    # using char for now in case not all numeric
    pub_date = models.CharField('Publication Date', max_length=255)
    #: number of pages in the work
    page_count = models.PositiveIntegerField(null=True, blank=True)
    #: date added to the archive
    added = models.DateTimeField(auto_now_add=True)
    #: date of last modification of the local record
    updated = models.DateTimeField(auto_now=True)






