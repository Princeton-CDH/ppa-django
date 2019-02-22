import logging
import os.path
import re
from zipfile import ZipFile

from cached_property import cached_property
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from eulxml.xmlmap import load_xmlobject_from_file
from flags import Flags
from pairtree import pairtree_path, pairtree_client, storage_exceptions
import requests
from wagtail.core.fields import RichTextField
from wagtail.admin.edit_handlers import FieldPanel
from wagtail.snippets.models import register_snippet

from ppa.archive.hathi import HathiBibliographicAPI, MinimalMETS
from ppa.archive.solr import Indexable
from ppa.archive.solr import PagedSolrQuery


logger = logging.getLogger(__name__)


#: label to use for items that are not in a collection
NO_COLLECTION_LABEL = 'Uncategorized'


class TrackChangesModel(models.Model):
    ''':class:`~django.modles.Model` mixin that keeps a copy of initial
    data in order to check if fields have been changed. Change detection
    only works on the current instance of an object.'''

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # store a copy of model data to allow for checking if
        # it has changed
        self.__initial = self.__dict__.copy()

    def save(self, *args, **kwargs):
        '''Saves data and reset copy of initial data.'''
        super().save(*args, **kwargs)
        # update copy of initial data to reflect saved state
        self.__initial = self.__dict__.copy()

    def has_changed(self, field):
        '''check if a field has been changed'''
        return getattr(self, field) != self.__initial[field]

    def initial_value(self, field):
        '''return the initial value for a field'''
        return self.__initial[field]


@register_snippet
class Collection(TrackChangesModel):
    '''A collection of :class:`ppa.archive.models.DigitizedWork` instances.'''
    #: the name of the collection
    name = models.CharField(max_length=255)
    #: a RichText description of the collection
    description = RichTextField(blank=True)
    #: flag to indicate collections to be excluded by default in
    #: public search
    exclude = models.BooleanField(default=False,
        help_text='Exclude by default on public search.')

    # configure for editing in wagtail admin
    panels = [
        FieldPanel('name'),
        FieldPanel('description'),
    ]

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    @property
    def name_changed(self):
        '''check if name has been changed (only works on current instance)'''
        return self.has_changed('name')

    @staticmethod
    def stats():
        '''Collection counts and date ranges, based on what is in Solr.
        Returns a dictionary where they keys are collection names and
        values are a dictionary with count and dates.
        '''

        # NOTE: if we *only* want counts, could just do a regular facet
        solr_stats = PagedSolrQuery({
            'q': '*:*',
            'facet': True,
            'facet.pivot': '{!stats=piv1}collections_exact',
            # NOTE: if we pivot on collection twice, like this, we should
            # have the information needed to generate a venn diagram
            # of the collections (based on number of overlap)
            # 'facet.pivot': '{!stats=piv1}collections_exact,collections_exact'
            'stats': True,
            'stats.field': '{!tag=piv1 min=true max=true}pub_date',
            # don't return any actual items, just the facets
            'rows': 0
        })
        facet_pivot = solr_stats.raw_response['facet_counts']['facet_pivot']
        # simplify the pivot stat data for display
        stats = {}
        for info in facet_pivot['collections_exact']:
            pub_date_stats = info['stats']['stats_fields']['pub_date']
            stats[info['value']] = {
                'count': info['count'],
                'dates': '%(min)d–%(max)d' % pub_date_stats \
                    if pub_date_stats['max'] != pub_date_stats['min'] \
                    else '%d' % pub_date_stats['min']
            }

        return stats


class ProtectedFlags(Flags):
    '''Flag set of fields that should be protected if edited in the admin.'''
    title = ()
    subtitle = ()
    sort_title = ()
    enumcron = ()
    author = ()
    pub_place = ()
    publisher = ()
    pub_date = ()

    @classmethod
    def deconstruct(cls):
        '''Give Django information needed to make
        :class:`ProtectedField.no_flags` default in migration.'''
        # (import path, [args], kwargs)
        return ('ppa.archive.models.ProtectedFlags', ['no_flags'], {})

    @classmethod
    def all_fields(cls):
        return list(ProtectedFlags.__members__.keys())

    def as_list(self):
        '''Return combined flags as a list of field names.'''
        all_fields = list(self.__members__.keys())
        return [field for field in all_fields
                if getattr(self, field)]

    def __str__(self):
        protected_fields = self.as_list()
        verbose_names = []
        for field in protected_fields:
            field = DigitizedWork._meta.get_field(field)
            # if the field has no actual verbose name, just capitalize
            # as does the Django admin
            # check against a version of field name with underscores replaced
            if field.verbose_name == field.name.replace('_', ' '):
                verbose_names.append(field.verbose_name.capitalize())
            else:
                # otherwise use the verbose_name verbatim
                verbose_names.append(field.verbose_name)
        return ', '.join(sorted(verbose_names))


class ProtectedFlagsField(models.Field):
    '''PositiveSmallIntegerField subclass that returns a
    :class:`ProtectedFlags` object and stores as integer.'''

    description = ('A field that stores an instance of :class:`ProtectedFlags` '
                   'as an integer.')

    def __init__(self, verbose_name=None, name=None, **kwargs):
        '''Make the field unnullable and not allowed to be blank.'''
        super().__init__(verbose_name, name, blank=False, null=False, **kwargs)

    def from_db_value(self, value, expression, connection, context):
        '''Always return an instance of :class:`ProtectedFlags`'''
        return ProtectedFlags(value)

    def get_internal_type(self):
        return 'PositiveSmallIntegerField'

    def get_prep_value(self, value):
        return int(value)

    def to_python(self, value):
        '''Always return an instance of :class:`ProtectedFlags`'''
        return ProtectedFlags(value)


class DigitizedWork(TrackChangesModel, Indexable):
    '''
    Record to manage digitized works included in PPA and store their basic
    metadata.
    '''
    HATHI = 'HT'
    OTHER = 'O'
    SOURCE_CHOICES = (
        (HATHI, 'HathiTrust'),
        (OTHER, 'Other'),
    )
    #: source of the record, HathiTrust or elsewhere
    source = models.CharField(
        max_length=2, choices=SOURCE_CHOICES, default=HATHI,
        help_text='Source of the record.')
    #: source identifier; hathi id for HathiTrust materials
    source_id = models.CharField(
        max_length=255, unique=True, verbose_name='Source ID',
        help_text='Source identifier. Unique identifier without spaces; ' +
                  'used for site URL. (HT id for HathiTrust materials.)')
    #: source url where the original can be accessed
    source_url = models.URLField(
        max_length=255, verbose_name='Source URL', blank=True,
        help_text='URL where the source item can be accessed')
    #: record id; for Hathi materials, used for different copies of
    #: the same work or for different editions/volumes of a work
    record_id = models.CharField(
        max_length=255, blank=True,
        help_text='For HathiTrust materials, record id (use to aggregate ' + \
                  'copies or volumes).')
    #: title of the work; using TextField to allow for long titles
    title = models.TextField(help_text='Main title')
    #: subtitle of the work; using TextField to allow for long titles
    subtitle = models.TextField(blank=True, default='',
                                help_text='Subtitle, if any (optional)')
    #: sort title: title without leading non-sort characters, from marc
    sort_title = models.TextField(
        default='',
        help_text='Sort title from MARC record or title without leading article')
    #: enumeration/chronology (hathi-specific)
    enumcron = models.CharField('Enumeration/Chronology', max_length=255,
                                blank=True)
    # TODO: what is the generic/non-hathi name for this? volume/version?

    # NOTE: may eventually to convert to foreign key
    author = models.CharField(
        max_length=255, blank=True,
        help_text='Authorized name of the author, last name first.')
    #: place of publication
    pub_place = models.CharField('Place of Publication', max_length=255,
                                 blank=True)
    #: publisher
    publisher = models.TextField(blank=True)
    # Needs to be integer to allow aggregating max/min, filtering by date
    pub_date = models.PositiveIntegerField('Publication Date', null=True, blank=True)
    #: number of pages in the work
    page_count = models.PositiveIntegerField(null=True, blank=True)
    #: public notes field for this work
    public_notes = models.TextField(blank=True, default='',
        help_text='Notes on edition or other details (displayed on public site)')
    #: internal team notes, not displayed on the public facing site
    notes = models.TextField(blank=True, default='',
        help_text='Internal curation notes (not displayed on public site)')
    #: metadata fields that should be preserved on bulk update because
    # they have been modified by data editors.
    protected_fields = ProtectedFlagsField(
        default=ProtectedFlags,
        help_text='Fields protected from bulk update because they have been '
                  'manually edited.'
    )
    #: collections that this work is part of
    collections = models.ManyToManyField(Collection, blank=True)
    #: date added to the archive
    added = models.DateTimeField(auto_now_add=True)
    #: date of last modification of the local record
    updated = models.DateTimeField(auto_now=True)

    PUBLIC = 'P'
    SUPPRESSED = 'S'
    STATUS_CHOICES = (
        (PUBLIC, 'Public'),
        (SUPPRESSED, 'Suppressed'),
    )
    #: status of record; currently choices are public or suppressed
    status = models.CharField(
        max_length=2, choices=STATUS_CHOICES, default=PUBLIC,
        help_text='Changing status to suppressed will remove rsync data ' +
        'for that volume and remove from the public index. This is ' +
        'currently not reversible; use with caution.')

    class Meta:
        ordering = ('sort_title',)

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
    def is_suppressed(self):
        '''Item has been suppressed (based on :attr:`status`).'''
        return self.status == self.SUPPRESSED

    def display_title(self):
        '''admin display title to allow displaying title but sorting on sort_title'''
        return self.title
    display_title.short_description = 'title'
    display_title.admin_order_field = 'sort_title'
    display_title.allow_tags = True

    def is_public(self):
        '''admin display field indicating if record is public or suppressed'''
        return self.status == self.PUBLIC
    is_public.short_description = 'Public'
    is_public.boolean = True
    is_public.admin_order_field = 'status'

    #: regular expresion for cleaning preliminary text from publisher names
    printed_by_re = r'^(Printed)?( and )?(Pub(.|lished|lisht)?)?( and sold)? (by|for|at)( the)? ?'
    # Printed by/for (the); Printed and sold by; Printed and published by;
    # Pub./Published/Publisht at/by/for the

    def save(self, *args, **kwargs):
        # if status has changed so that object is now suppressed and this
        # is a HathiTrust item, remove pairtree data
        if self.has_changed('status') and self.status == self.SUPPRESSED \
          and self.source == DigitizedWork.HATHI:
            self.delete_hathi_pairtree_data()

        # source id is used as Solr identifier; if it changes, remove
        # the old record from Solr before saving with the new identifier
        # NOTE: source id edit only supported for non-hathi content; should
        # be prevented by validation in clean method
        if self.has_changed('source_id'):
            new_source_id = self.source_id
            self.source_id = self.initial_value('source_id')
            self.remove_from_index(params={"commitWithin": 3000})
            self.source_id = new_source_id

        super().save(*args, **kwargs)

    def clean(self):
        '''Add custom validation to trigger a save error in the admin
        if someone tries to unsuppress a record that has been suppressed
        (not yet supported).'''
        if self.has_changed('status') and self.status != self.SUPPRESSED:
            raise ValidationError('Unsuppressing records not yet supported.')

        # should not be editable in admin, but add a validation check
        # just in case
        if self.has_changed('source_id') and self.source == self.HATHI:
            raise ValidationError('Changing source ID for HathiTrust records is not supported')

    def populate_from_bibdata(self, bibdata):
        '''Update record fields based on Hathi bibdata information.
        Full record is required in order to set all fields

        :param bibdata: bibliographic data returned from HathiTrust
            as instance of :class:`ppa.archive.hathi.HathiBibliographicRecord`

        '''
        # store hathi record id
        self.record_id = bibdata.record_id
        print(bool(bibdata.marcxml))

        # set fields from marc if available, since it has more details
        if bibdata.marcxml:

            # set title and subtitle from marc if possible
            # - clean title: strip trailing space & slash and initial bracket
            if not self.protected_fields.title:
                self.title = bibdata.marcxml['245']['a'].rstrip(' /') \
                    .lstrip('[')

            # according to PUL CAMS,
            # 245 subfield contains the subtitle *if* the preceding field
            # ends with a colon. (Otherwise could be a parallel title,
            # e.g. title in another language).
            # HOWEVER: metadata from Hathi doesn't seem to follow this
            # pattern (possibly due to records being older?)

            # subfields is a list of code, value, code, value
            # iterate in paired steps of two starting with first and second
            # for code, value in zip(bibdata.marcxml['245'].subfields[0::2],
            #                        bibdata.marcxml['245'].subfields[1::2]):
            #     if code == 'b':
            #         break
            #     preceding_character = value[-1:]

            # if preceding_character == ':':
            #     self.subtitle = bibdata.marcxml['245']['b'] or ''
            if not self.protected_fields.subtitle:
                # NOTE: skipping preceding character check for now
                self.subtitle = bibdata.marcxml['245']['b'] or ''
                # strip trailing space & slash from subtitle
                self.subtitle = self.subtitle.rstrip(' /')

            # indicator 2 provides the number of characters to be
            # skipped when sorting (could be 0)
            try:
                non_sort = int(bibdata.marcxml['245'].indicators[1])
            except ValueError:
                # at least one record has a space here instead of a number
                # probably a data error, but handle it
                # - assuming no non-sort characters
                non_sort = 0

            # strip whitespace, since a small number of records have a
            # nonsort value that doesn't include a space after a
            # definite article.
            # Also strip punctuation, since MARC only includes it in
            # non-sort count when there is a definite article.
            if not self.protected_fields.sort_title:
                self.sort_title = bibdata.marcxml.title()[non_sort:]\
                    .strip(' "[')
            if not self.protected_fields.author:
                self.author = bibdata.marcxml.author() or ''
                # remove a note present on some records and strip whitespace
                self.author = self.author.replace('[from old catalog]', '').strip()
                # removing trailing period, except when it is part of an
                # initial or known abbreviation (i.e, Esq.)
                # Look for single initial, but support initials with no spaces
                if self.author.endswith('.') and not \
                re.search(r'( ([A-Z]\.)*[A-Z]| Esq)\.$', self.author):
                    self.author = self.author.rstrip('.')

            # field 260 includes publication information
            if '260' in bibdata.marcxml:
                if not self.protected_fields.pub_place:
                    # strip trailing punctuation from publisher and pub place

                    # subfield $a is place of publication
                    self.pub_place = bibdata.marcxml['260']['a'] or ''
                    self.pub_place = self.pub_place.rstrip(';:,')
                    # if place is marked as unknown ("sine loco"), leave empty
                    if self.pub_place.lower() == '[s.l.]':
                        self.pub_place = ''
                if not self.protected_fields.publisher:
                    # subfield $b is name of publisher
                    self.publisher = bibdata.marcxml['260']['b'] or ''
                    self.publisher = self.publisher.rstrip(';:,')
                    # if publisher is marked as unknown ("sine nomine"), leave empty
                    if self.publisher.lower() == '[s.n.]':
                        self.publisher = ''

            if not self.protected_fields.publisher:
                # remove printed by statement before publisher name
                self.publisher = re.sub(self.printed_by_re, '', self.publisher,
                    flags=re.IGNORECASE)

            # maybe: consider getting volume & series directly from
            # marc rather than relying on hathi enumcron ()

        else:
            # fallback behavior, if marc is not availiable
            # use dublin core title
            if not self.protected_fields.title:
                self.title = bibdata.title
            # could guess at non-sort, but hopefully unnecessary

        # NOTE: might also want to store sort title
        # pub date returned in api JSON is list; use first for now (if available)
        if not self.protected_fields.pub_date:
            if bibdata.pub_dates:
                self.pub_date = bibdata.pub_dates[0]
        copy_details = bibdata.copy_details(self.source_id)
        # hathi version/volume information for this specific copy of a work
        if not self.protected_fields.enumcron:
            self.enumcron = copy_details['enumcron'] or ''
        # hathi source url can currently be inferred from htid, but is
        # included in the bibdata in case it changes - so let's just store it
        self.source_url = copy_details['itemURL']

        if not self.protected_fields.publisher:
        # remove brackets around inferred publishers, place of publication
        # *only* if they wrap the whole text
            self.publisher = re.sub(r'^\[(.*)\]$', r'\1', self.publisher)
        if not self.protected_fields.pub_place:
            self.pub_place = re.sub(r'^\[(.*)\]$', r'\1', self.pub_place)

        # should also consider storing:
        # - last update, rights code / rights string, item url
        # (maybe solr only?)

    def handle_collection_save(sender, instance, **kwargs):
        '''signal handler for collection save; reindex associated digitized works'''
        # only reindex if collection name has changed
        # and if collection has already been saved
        if instance.pk and instance.name_changed:
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

        # When an item has been suppressed, return id only.
        # This will blank out any previously indexed values, and item
        # will not be findable by any public searchable fields.
        if self.status == self.SUPPRESSED:
            return {'id': self.source_id}

        return {
            'id': self.source_id,
            'source_id': self.source_id,
            'source_url': self.source_url,
            'title': self.title,
            'subtitle': self.subtitle,
            'sort_title': self.sort_title,
            'pub_date': self.pub_date,
            'pub_place': self.pub_place,
            'publisher': self.publisher,
            'enumcron': self.enumcron,
            'author': self.author,
            # set default value to simplify queries to find uncollected items
            # (not set in Solr schema because needs to be works only)
            'collections':
                [collection.name for collection in self.collections.all()]
                if self.collections.exists()
                else [NO_COLLECTION_LABEL],
            # public notes field for display on site_name
            'notes': self.public_notes,
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

    def hathi_pairtree_client(self):
        '''Initialize a pairtree client for the pairtree datastore this
         object belongs to, based on its Hathi prefix id.'''
        return pairtree_client.PairtreeStorageClient(
            self.hathi_prefix,
            os.path.join(settings.HATHI_DATA, self.hathi_prefix))

    def hathi_pairtree_object(self, ptree_client=None):
        '''get a pairtree object for the current work

        :param ptree_client: optional
            :class:`pairtree_client.PairtreeStorageClient` if one has
            already been initialized, to avoid repeated initialization
            (currently used in hathi_import manage command)
        '''
        if ptree_client is None:
            # get pairtree client if not passed in
            ptree_client = self.hathi_pairtree_client()

        # return the pairtree object for current work
        return ptree_client.get_object(self.hathi_pairtree_id,
                                       create_if_doesnt_exist=False)

    def delete_hathi_pairtree_data(self):
        '''Delete pairtree object from the pairtree datastore.'''
        logger.info('Deleting pairtree data for %s', self.source_id)
        try:
            self.hathi_pairtree_client() \
                .delete_object(self.hathi_pairtree_id)
        except storage_exceptions.ObjectNotFoundException:
            # data is already gone; warn, but not an error
            logger.warning('Pairtree deletion failed; object not found %s',
                        self.source_id)

    def _hathi_content_path(self, ext, ptree_client=None):
        '''path to zipfile within the hathi contents for this work'''
        pairtree_obj = self.hathi_pairtree_object(ptree_client=ptree_client)
        # - expect a mets file and a zip file
        # NOTE: not yet making use of the metsfile
        # - don't rely on them being returned in the same order on every machine
        parts = pairtree_obj.list_parts(self.hathi_content_dir)
        # find the first zipfile in the list (should only be one)
        filepath = [part for part in parts if part.endswith(ext)][0]

        return os.path.join(pairtree_obj.id_to_dirpath(),
                            self.hathi_content_dir, filepath)

    def hathi_zipfile_path(self, ptree_client=None):
        '''path to zipfile within the hathi contents for this work'''
        return self._hathi_content_path('zip', ptree_client=ptree_client)

    def hathi_metsfile_path(self, ptree_client=None):
        '''path to mets xml file within the hathi contents for this work'''
        return self._hathi_content_path('.mets.xml', ptree_client=ptree_client)

    def page_index_data(self):
        '''Get page content for this work from Hathi pairtree and return
        data to be indexed in solr.'''

        # If an item has been suppressed or is from a source other than
        # hathi, bail out. No pages to index.
        if self.is_suppressed or self.source != self.HATHI:
            return

        # load mets record to pull metadata about the images
        try:
            mmets = load_xmlobject_from_file(self.hathi_metsfile_path(),
                                             MinimalMETS)
        except storage_exceptions.ObjectNotFoundException:
            logger.error('Pairtree data for %s not found but status is %s',
                         self.source_id, self.get_status_display())
            return

        # read zipfile contents in place, without unzipping
        with ZipFile(self.hathi_zipfile_path()) as ht_zip:

            # yield a generator of index data for each page; iterate
            # over pages in METS structmap
            for page in mmets.structmap_pages:

                pagefilename = os.path.join(self.hathi_content_dir, page.text_file_location)
                with ht_zip.open(pagefilename) as pagefile:
                    try:
                        yield {
                            'id': '%s.%s' % (self.source_id, page.text_file.sequence),
                            'source_id': self.source_id,   # for grouping with work record
                            'content': pagefile.read().decode('utf-8'),
                            'order': page.order,
                            'label': page.display_label,
                            'tags': page.label.split(', ') if page.label else [],
                            'item_type': 'page'
                        }
                    except StopIteration:
                        return

    def get_metadata(self, metadata_format):
        '''Get metadata for this item in the specified format.
        Currently only supports marc.'''
        if metadata_format == 'marc':
            # get metadata from hathi bib api and serialize
            # as binary marc
            if self.source == DigitizedWork.HATHI:
                bib_api = HathiBibliographicAPI()
                bibdata = bib_api.record('htid', self.source_id)
                return bibdata.marcxml.as_marc()

            # TBD: can we get MARC records from oclc?
            # or should we generate dublin core from db metadata?

            return ''

        # error for unknown
        raise ValueError('Unsupported format %s' % metadata_format)
