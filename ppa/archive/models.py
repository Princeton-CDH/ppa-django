import logging
import os.path
import re
from zipfile import ZipFile

from cached_property import cached_property
from django.conf import settings
from django.db import models
from django.urls import reverse
from eulxml.xmlmap import load_xmlobject_from_file
from pairtree import pairtree_path, pairtree_client
from wagtail.core.fields import RichTextField
from wagtail.admin.edit_handlers import FieldPanel
from wagtail.snippets.models import register_snippet

from ppa.archive.hathi import HathiBibliographicAPI, MinimalMETS
from ppa.archive.solr import Indexable
from ppa.archive.solr import PagedSolrQuery


logger = logging.getLogger(__name__)


@register_snippet
class Collection(models.Model):
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
    #: record id; for Hathi materials, used for different copies of
    #: the same work or for different editions/volumes of a work
    record_id = models.CharField(
        max_length=255,
        help_text='For HathiTrust materials, record id (use to aggregate ' + \
                  'copies or volumes).')
    #: title of the work; using TextField to allow for long titles
    title = models.TextField(help_text='Main title')
    #: subtitle of the work; using TextField to allow for long titles
    subtitle = models.TextField(blank=True, default='',
                                help_text='Subtitle, if any (optional)')
    #: sort title: title without leading non-sort characters, from marc
    sort_title = models.TextField(default='',
                                  help_text='Sort title from MARC record')
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
    public_notes = models.TextField(blank=True, default='',
        help_text='Notes on edition or other details (displayed on public site)')
    #: internal team notes, not displayed on the public facing site
    notes = models.TextField(blank=True, default='',
        help_text='Internal curation notes (not displayed on public site)')
    #: collections that this work is part of
    collections = models.ManyToManyField(Collection, blank=True)
    #: date added to the archive
    added = models.DateTimeField(auto_now_add=True)
    #: date of last modification of the local record
    updated = models.DateTimeField(auto_now=True)

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
    def srcid(self):
        '''alias for :attr:`source_id` for consistency with solr attributes'''
        # hopefully temporary workaround until solr fields made consistent
        return self.source_id

    @property
    def src_url(self):
        '''alias for :attr:`source_url` for consistency with solr attributes'''
        # hopefully temporary workaround until solr fields made consistent
        return self.source_url

    def display_title(self):
        '''admin display title to allow displaying title but sorting on sort_title'''
        return self.title
    display_title.short_description = 'title'
    display_title.admin_order_field = 'sort_title'
    display_title.allow_tags = True

    #: regular expresion for cleaning preliminary text from publisher names
    printed_by_re = r'^(Printed)?( and )?(Pub(.|lished|lisht)?)?( and sold)? (by|for|at)( the)? ?'
    # Printed by/for (the); Printed and sold by; Printed and published by;
    # Pub./Published/Publisht at/by/for the

    def populate_from_bibdata(self, bibdata):
        '''Update record fields based on Hathi bibdata information.
        Full record is required in order to set all fields

        :param bibdata: bibliographic data returned from HathiTrust
            as instance of :class:`ppa.archive.hathi.HathiBibliographicRecord`

        '''
        # store hathi record id
        self.record_id = bibdata.record_id

        # set fields from marc if available, since it has more details
        if bibdata.marcxml:
            # set title and subtitle from marc if possible
            # - clean title: strip trailing space & slash and initial bracket
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
            self.sort_title = bibdata.marcxml.title()[non_sort:].strip(' "[')

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
                # strip trailing punctuation from publisher and pub place

                # subfield $a is place of publication
                self.pub_place = bibdata.marcxml['260']['a'] or ''
                self.pub_place = self.pub_place.rstrip(';:,')
                # if place is marked as unknown ("sine loco"), leave empty
                if self.pub_place.lower() == '[s.l.]':
                    self.pub_place = ''

                # subfield $b is name of publisher
                self.publisher = bibdata.marcxml['260']['b'] or ''
                self.publisher = self.publisher.rstrip(';:,')
                # if publisher is marked as unknown ("sine nomine"), leave empty
                if self.publisher.lower() == '[s.n.]':
                    self.publisher = ''

            # remove printed by statement before publisher name
            self.publisher = re.sub(self.printed_by_re, '', self.publisher,
                flags=re.IGNORECASE)

            # maybe: consider getting volume & series directly from
            # marc rather than relying on hathi enumcron ()

        else:
            # fallback behavior, if marc is not availiable
            # use dublin core title
            self.title = bibdata.title
            # could guess at non-sort, but hopefully unnecessary

        # NOTE: might also want to store sort title
        # pub date returned in api JSON is list; use first for now (if available)
        if bibdata.pub_dates:
            self.pub_date = bibdata.pub_dates[0]
        copy_details = bibdata.copy_details(self.source_id)
        # hathi version/volume information for this specific copy of a work
        self.enumcron = copy_details['enumcron'] or ''
        # hathi source url can currently be inferred from htid, but is
        # included in the bibdata in case it changes - so let's just store it
        self.source_url = copy_details['itemURL']

        # remove brackets around inferred publishers, place of publication
        # *only* if they wrap the whole text
        self.publisher = re.sub(r'^\[(.*)\]$', r'\1', self.publisher)
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
        return {
            'id': self.source_id,
            'srcid': self.source_id,
            'src_url': self.source_url,
            'title': self.title,
            'subtitle': self.subtitle,
            'sort_title': self.sort_title,
            'pub_date': self.pub_date,
            'pub_place': self.pub_place,
            'publisher': self.publisher,
            'enumcron': self.enumcron,
            'author': self.author,
            'collections': [collection.name for collection
                            in self.collections.all()],
            # general purpose multivalued field, currently only
            # includes public notes in this method, other fields
            # copied in Solr schema.
            'text': [self.public_notes],
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

        # load mets record to pull metadata about the images
        mmets = load_xmlobject_from_file(self.hathi_metsfile_path(),
                                         MinimalMETS)

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
                            'srcid': self.source_id,   # for grouping with work record
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
            bib_api = HathiBibliographicAPI()
            bibdata = bib_api.record('htid', self.source_id)
            return bibdata.marcxml.as_marc()

        # error for unknown
        raise ValueError('Unsupported format %s' % metadata_format)
