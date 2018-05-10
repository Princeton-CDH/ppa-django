import csv
import json
import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils.http import urlencode
from django.utils.timezone import now
from django.urls import reverse
from django.views.generic import ListView, DetailView
from django.views.generic.edit import FormView
from SolrClient.exceptions import SolrError

from ppa.archive.forms import SearchForm, AddToCollectionForm
from ppa.archive.models import DigitizedWork, Collection
from ppa.archive.solr import get_solr_connection, PagedSolrQuery


logger = logging.getLogger(__name__)


class DigitizedWorkListView(ListView):
    '''Search and browse digitized works.  Based on Solr index
    of works and pages.'''

    template_name = 'archive/list_digitizedworks.html'
    form_class = SearchForm
    # NOTE: listview would be nice, but would have to figure out how to
    # make solrclient compatible with django pagination

    paginate_by = 50

    # keyword query; assume no search terms unless set
    query = None

    def get_queryset(self, **kwargs):
        form_opts = self.request.GET.copy()
        # Check for a nonsensical search with 'relevance' and no query string
        if 'query' not in form_opts or not form_opts['query']:
            if 'sort' in form_opts and form_opts['sort'] == 'relevance':
                del form_opts['sort']

        for key, val in self.form_class.defaults.items():
            # set as list to avoid nested lists
            # follows solution using in derrida-django for InstanceListView
            if isinstance(val, list):
                form_opts.setlistdefault(key, val)
            else:
                form_opts.setdefault(key, val)

        # NOTE: Default sort for keyword search should be relevance but
        # currently no way to distinguish default sort from user selected
        self.form = self.form_class(form_opts)

        # if the form is not valid, return an empty queryset and bail out
        # (queryset needed for django paginator)
        if not self.form.is_valid():
            return DigitizedWork.objects.none()

        solr_q = join_q = collections = sort = None
        if self.form.is_valid():
            search_opts = self.form.cleaned_data
            self.query = search_opts.get("query", "")
            sort = search_opts.get("sort", "")
            # NOTE: This allows us to get the name of collections for
            # collections_exact and set collections to a list of collection names
            collections = search_opts.get("collections", None)

        # solr supports multiple filter queries, and documents must
        # match all of them; collect them as a list to allow multiple
        filter_q = []

        coll_query = ''
        # use filter query to restrict by collection if specified
        if collections:
            # OR to allow multiple; quotes to handle multiword collection names
            coll_query = 'collections_exact:(%s)' % \
                (' OR '.join(['"%s"' % coll for coll in collections]))
            # work in collection or page associated with work in collection
            filter_q.append('(%(coll)s OR {!join from=id to=srcid v=$coll_query})' \
                % {'coll': coll_query})

        if self.query:
            # simple keyword search across all text content
            solr_q = join_q = "text:(%s)" % self.query

            # use join to ensure we always get the work if any pages match
            # using query syntax as documented at
            # http://comments.gmane.org/gmane.comp.jakarta.lucene.solr.user/95646
            # to support exact phrase searches
            solr_q = 'text:(%s) OR {!join from=srcid to=id v=$join_query}' % self.query
            # sort by relevance, return score for display
        else:
            solr_q = '*:*'

        self.sort, solr_sort = self.form.get_solr_sort_field(sort)

        fields = '*,score'
        # NOTE: For now, defaulting to always including score in fields

        logger.debug("Solr search query: %s", solr_q)

        # use filter query to collapse works and pages into groups
        # sort so work is first, then by page order
        filter_q.append('{!collapse field=srcid sort="order asc"}')

        range_opts = {
            'facet.range': self.form.range_facets
        }
        for range_facet in self.form.range_facets:
            # range filter requested in search options
            start = end = None
            # if start or end is specified on the form, add a filter query
            if range_facet in search_opts and search_opts[range_facet]:
                start, end = search_opts[range_facet].split('-')
                range_filter = '[%s TO %s]' % (start or '*', end or '*')
                filter_q.append('%s:%s' % (range_facet, range_filter))

            # get minimum and maximum pub date values from the db
            pubmin, pubmax = self.form.pub_date_minmax()

            # NOTE: hard-coded values are fallback logic for when
            # no contents are in the datbase and pubmin/pubmax are None
            start = int(start) if start else pubmin or 0
            end = int(end) if end else pubmax or 1922

            # Configure range facet options specific to current field, to
            # support more than one range facet (even though not currently needed)
            range_opts.update({
                # current range filter
                'f.%s.facet.range.start' % range_facet: start,
                # 'start': int(start) if start else ranges['%s_min' % range_facet],
                # 'end': int(end) if end else ranges['%s_max' % range_facet],
                'f.%s.facet.range.end' % range_facet: end,
                # calculate gap based start and end & desired number of slices
                # ideally, generate 24 slices; minimum gap size of 1
                'f.%s.facet.range.gap' % range_facet: max(1, int((end - start) / 24)),
                # restrict last range to *actual* maximum value
                'f.%s.facet.range.hardend' % range_facet: True
            })

        # basic solr options, including filter query
        solr_opts = {
            'q': solr_q,
            'sort': solr_sort,
            'fl': fields,
            'fq': filter_q,
            # turn on faceting and add any self.form facet_fields
            'facet': 'true',
            'facet.field': [field for field in self.form.facet_fields],
            # default expand sort is score desc
            'expand': 'true',
            'expand.rows': 2,   # number of items in the collapsed group, i.e pages to display
            'join_query': join_q,
            'coll_query': coll_query,
            'rows': 50  # override solr default of 10 results; display 50 at a time for now
        }

        # add facet range options to the solr options
        solr_opts.update(range_opts)

        self.solrq = PagedSolrQuery(solr_opts)

        return self.solrq

    def get_page_highlights(self, page_groups):
         # If there is a keyword search, query Solr for matching pages
        # with text highlighting.  Note that this has to be done as
        # a separate query because Solr doesn't support highlighting on
        # collapsed items.

        page_highlights = {}
        if not self.query or not page_groups:
            # if there is no keyword query, bail out
            return page_highlights

        # generate a list of page ids from the grouped results
        page_ids = [page['id'] for results in page_groups.values()
                    for page in results['docs']]

        if not page_ids:
            # if no page ids were found, bail out
            return page_highlights

        # Query solr for the desired pages by id with the same
        # keyword search.
        # NOTE: This id query assumes OR is default; if  that changes,
        # add an explicitly OR here between ids.
        # NOTE 2: using quotes around ids to handle ids that include
        # colons, e.g. ark:/foo/bar .
        solr_pageq = PagedSolrQuery({
            'q': 'text:(%s) AND id:(%s)' % \
                (self.query, ' '.join('"%s"' % pid for pid in page_ids)),
            # enable highlighting on content field with 3 snippets
            'hl': True,
            'hl.fl': 'content',
            'hl.snippets': 3,
            # use Unified Highlighter (not default but recommended)
            'hl.method': 'unified',
            # override solr default of 10 results to return all pages
            'rows': len(page_ids)
        })
        return solr_pageq.get_highlighting()

    def get_context_data(self, **kwargs):
        # if the form is not valid, bail out
        if not self.form.is_valid():
            context = super(DigitizedWorkListView, self).get_context_data(**kwargs)
            context['search_form'] = self.form
            return context

        page_groups = facet_ranges = None
        try:
            # catch an error querying solr when the search terms cannot be parsed
            # (e.g., incomplete exact phrase)
            context = super(DigitizedWorkListView, self).get_context_data(**kwargs)
            page_groups = self.solrq.get_expanded()
            facet_dict = self.solrq.get_facets()

            self.form.set_choices_from_facets(facet_dict)
            # needs to be inside try/catch or it will re-trigger any error
            facet_ranges = self.solrq.get_facets_ranges()
        except SolrError as solr_err:
            context = {'object_list': []}
            if 'Cannot parse' in str(solr_err):
                error_msg = 'Unable to parse search query; please revise and try again.'
            else:
                # NOTE: this error should possibly be raised; 500 error?
                error_msg = 'Something went wrong.'
            context['error'] = error_msg

        # pass in query to context so that it can be used in the template
        query = self.request.GET.get('query', '')

        context.update({
            'search_form': self.form,
            # total and object_list provided by paginator
            'sort': self.sort,
            'page_groups': page_groups,
            # range facet data for publication date
            'facet_ranges': facet_ranges,
            'page_highlights': self.get_page_highlights(page_groups),
            # query for use template links to detail view with search
            'query': query,
        })
        return context


class DigitizedWorkDetailView(DetailView):
    '''Display details for a single digitized work'''
    model = DigitizedWork
    slug_field = 'source_id'
    slug_url_kwarg = 'source_id'


class CollectionListView(ListView):
    '''
    Display list of public-facing :class:`ppa.archive.models.Collection`
    instances
    '''
    model = Collection
    # NOTE: For consistency with DigitizedWork's list view
    template_name = 'archive/list_collections.html'
    ordering = ('name',)


class DigitizedWorkCSV(ListView):
    '''Export of digitized work details as CSV download.'''
    # NOTE: csv logic could be extracted as a view mixin for reuse
    model = DigitizedWork
    # order by id for now, for simplicity
    ordering = 'id'
    header_row = ['Database ID', 'Source ID', 'Title', 'Author',
                  'Publication Date', 'Publication Place', 'Publisher',
                  'Enumcron', 'Collection', 'Page Count', 'Date Added',
                  'Last Updated']

    def get_csv_filename(self):
        '''Return the CSV file name based on the current datetime.

        :returns: the filename for the CSV to be generated
        :rtype: str
        '''
        return 'ppa-digitizedworks-%s.csv' % now().strftime('%Y%m%dT%H:%M:%S')

    def get_data(self):
        '''Get data for the CSV.

        :returns: rows for CSV columns
        :rtype: tuple
        '''
        return ((dw.id, dw.source_id, dw.title, dw.author,
                 dw.pub_date, dw.pub_place, dw.publisher, dw.enumcron,
                 ';'.join([coll.name for coll in dw.collections.all()]),
                 dw.page_count, dw.added, dw.updated
                 )
                for dw in self.get_queryset().prefetch_related('collections'))
        # NOTE: prefetch collections so they are retrieved more efficiently
        # all at once, rather than one at a time for each item

    def render_to_csv(self, data):
        '''
        Render the CSV as an HTTP response.

        :rtype: :class:`django.http.HttpResponse`
        '''
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="%s"' % \
            self.get_csv_filename()

        writer = csv.writer(response)
        writer.writerow(self.header_row)
        for row in data:
            writer.writerow(row)
        return response

    def get(self, *args, **kwargs):
        '''Return CSV file on GET request.'''
        return self.render_to_csv(self.get_data())


class AddToCollection(ListView, FormView):
    '''
    View to bulk add a queryset of :class:`ppa.archive.models.DigitizedWork`
    to a set of :class:`ppa.archive.models.Collection instances`.

    Restricted to staff users via staff_member_required on url.
    '''

    model = DigitizedWork
    template_name = 'archive/add_to_collection.html'
    form_class = AddToCollectionForm

    def get_success_url(self):
        '''
        Redirect to the :class:`ppa.archive.models.DigitizedWork`
        change_list in the Django admin with pagination and filters preserved.
        Expects :meth:`ppa.archive.admin.bulk_add_collection`
        to have set 'collection-add-filters' as a dict in the request's
        session.
        '''
        change_list = reverse('admin:archive_digitizedwork_changelist')
        # get request.session's querystring filter, and if it exists
        # use it to set the querystring
        querystring = ''
        filter_dict = self.request.session.get('collection-add-filters', None)
        if filter_dict:
            querystring = '?%s' % urlencode(filter_dict)
        return '%s%s' % (change_list, querystring)

    def get_queryset(self, *args, **kwargs):
        '''Return a queryset filtered by id, or empty list if no ids'''
        # get ids from session if there are any
        ids = self.request.session.get('collection-add-ids', [])
        # if somehow a problematic non-pk is pushed, will be ignored in filter
        digworks = DigitizedWork.objects.filter(id__in=ids
                                                if ids else []).order_by('id')
        # revise the stored list in session to eliminate any pks
        # that don't exist
        self.request.session['collection-add-ids'] = \
            list(digworks.values_list('id', flat=True))
        return digworks

    def post(self, request, *args, **kwargs):
        '''
        Add :class:`ppa.archive.models.DigitizedWork` instances passed in form
        data to selected instances of :class:`ppa.archive.models.Collection`,
        then return to change_list view.

        Expects a list of DigitizedWork ids to be set in the request session.

        '''
        form = AddToCollectionForm(request.POST)
        if form.is_valid() and request.session['collection-add-ids']:
            data = form.cleaned_data
            # get digitzed works from validated form
            digitized_works = self.get_queryset()
            del request.session['collection-add-ids']
            for collection in data['collections']:
                # add rather than set to ensure add does not replace
                # previous digitized works in set.
                collection.digitizedwork_set.add(*digitized_works)
            # reindex solr with the new collection data
            solr_docs = [work.index_data() for work in digitized_works]
            solr, solr_collection = get_solr_connection()
            solr.index(solr_collection, solr_docs,
                       params={'commitWithin': 2000})
            # create a success message to add to message framework stating
            # what happened
            num_works = digitized_works.count()
            collections = ', '.join(collection.name for
                                    collection in data['collections'])
            messages.success(request, 'Successfully added %d works to: %s.'
                             % (num_works, collections))
            # redirect to the change list with the message intact
            return redirect(self.get_success_url())
        # make form error more descriptive, default to an error re: pks
        if 'collections' in form.errors:
            del form.errors['collections']
            form.add_error(
                'collections',
                ValidationError('Please select at least one Collection')
            )
        # Provide an object list for ListView and emulate CBV calling
        # render_to_response to pass form with errors; just calling super
        # doesn't pass the form with error set
        self.object_list = self.get_queryset()
        return self.render_to_response(self.get_context_data(form=form))
