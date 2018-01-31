import csv
import json
import logging

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils.timezone import now
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView
from django.views.generic.edit import FormMixin, ProcessFormView
from SolrClient.exceptions import SolrError

from ppa.archive.forms import SearchForm, BulkAddCollectionForm
from ppa.archive.models import DigitizedWork, Collection
from ppa.archive.solr import PagedSolrQuery


logger = logging.getLogger(__name__)


class DigitizedWorkListView(ListView):
    '''Search and browse digitized works.  Based on Solr index
    of works and pages.'''

    template_name = 'archive/list_digitizedworks.html'
    # NOTE: listview would be nice, but would have to figure out how to
    # make solrclient compatible with django pagination

    paginate_by = 50

    def get_queryset(self, **kwargs):
        self.form = SearchForm(self.request.GET)
        query = join_q = collections = None
        if self.form.is_valid():
            query = self.form.cleaned_data.get("query", "")
            # NOTE: This allows us to get the name of collections for
            # collections_exact and set collections to a list of collection names
            collections = self.form.cleaned_data.get("collections", None)

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

        if query:
            # simple keyword search across all text content
            solr_q = join_q = "text:(%s)" % query

            # use join to ensure we always get the work if any pages match
            # using query syntax as documented at
            # http://comments.gmane.org/gmane.comp.jakarta.lucene.solr.user/95646
            # to support exact phrase searches
            solr_q = 'text:(%s) OR {!join from=srcid to=id v=$join_query}' % query
            # sort by relevance, return score for display
            self.sort = 'relevance'
            solr_sort = 'score desc'
            fields = '*,score'
        else:
            # no search term - find everything
            solr_q = "*:*"
            # for now, use title for default sort
            self.sort = 'title'
            solr_sort = 'title_exact asc'
            fields = '*'

        logger.debug("Solr search query: %s", solr_q)

        # use filter query to collapse works and pages into groups
        # sort so work is first, then by page order
        filter_q.append('{!collapse field=srcid sort="order asc"}')

        self.solrq = PagedSolrQuery({
            'q': solr_q,
            'sort': solr_sort,
            'fl': fields,
            'fq': filter_q,
            # turn on faceting and add any self.form facet_fields
            'facet': 'true',
            'facet.field': [field for field in self.form.facet_fields],
            # default expand sort is score desc
            'expand': 'true',
            'expand.rows': 10,   # number of items in the collapsed group, i.e pages to display
            'join_query': join_q,
            'coll_query': coll_query
            # 'rows': 50  # override solr default of 10 results; display 50 at a time for now
        })

        return self.solrq

    def get_context_data(self, **kwargs):
        page_groups = None
        try:
            # catch an error querying solr when the search terms cannot be parsed
            # (e.g., incomplete exact phrase)
            context = super(DigitizedWorkListView, self).get_context_data(**kwargs)
            page_groups = json.loads(self.solrq.get_json()).get('expanded', {})
            facet_dict = self.solrq.get_facets()
            self.form.set_choices_from_facets(facet_dict)

        except SolrError as solr_err:
            context = {'object_list': []}
            if 'Cannot parse' in str(solr_err):
                error_msg = 'Unable to parse search query; please revise and try again.'
            else:
                error_msg = 'Something went wrong.'
            context = {'object_list': [], 'error': error_msg}

        context.update({
            'search_form': self.form,
            # total and object_list provided by paginator
            'sort': self.sort,
            'page_groups': page_groups

        })
        return context


class DigitizedWorkDetailView(DetailView):
    '''Display details for a single digitized work'''
    model = DigitizedWork
    slug_field = 'source_id'
    slug_url_kwarg = 'source_id'


class CollectionListView(ListView):
    '''Display list of public-facing :class:ppa.archive.models.Collection instances'''
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
    header_row = ['Database ID', 'Source ID', 'Title', 'Author', 'Publication Date',
        'Publication Place', 'Publisher', 'Enumcron']

    def get_csv_filename(self):
        return 'ppa-digitizedworks-%s.csv' % now().strftime('%Y%m%dT%H:%M:%S')

    def get_data(self):
        return ((dw.id, dw.source_id, dw.title, dw.author,
                 dw.pub_date, dw.pub_place, dw.publisher, dw.enumcron)
                for dw in self.get_queryset())

    def render_to_csv(self, data):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="%s"' % \
            self.get_csv_filename()

        writer = csv.writer(response)
        writer.writerow(self.header_row)
        for row in data:
            writer.writerow(row)
        return response

    def get(self, *args, **kwargs):
        return self.render_to_csv(self.get_data())


class BulkAddCollectionView(ListView, FormMixin, ProcessFormView):
    '''
    View to bulk add a queryset of :class:ppa.archive.models.DigitizedWork
    to a set of :class:ppa.archive.models.Collection instances.
    '''

    model = DigitizedWork
    template_name = 'admin/archive/digitizedwork/bulk_add_collections.html'
    form_class = BulkAddCollectionForm
    success_url = reverse_lazy('admin:archive_digitizedwork_changelist')

    def get_queryset(self, *args, **kwargs):
        '''Return a queryset filtered by id, or empty list if no ids'''
        ids = self.request.GET.get('ids', None)
        if ids:
            return DigitizedWork.objects.filter(id__in=ids.split(','))
        return []

    def get_initial(self):
        '''
        Set the hidden field with the :class:ppa.archive.models.DigitizedWork
        to add to collection(s) to pass to POST request.
        '''
        initial = super(BulkAddCollectionView, self).get_initial()
        ids = self.request.GET.get('ids', None)
        if ids:
            initial['digitized_work_ids'] = ids
        return initial

    def post(self, request, *args, **kwargs):
        '''
        Add :class:ppa.archive.models.DigitizedWork instances passed in form
        data to selected instances of :class:ppa.archive.models.Collection,
        then return to change_list view.
        '''
        form = BulkAddCollectionForm(request.POST)
        # override default post functionality to set collections
        if form.is_valid():
            data = form.cleaned_data
            ids = data['digitized_work_ids'].split(',')
            # get digitzed works from validated form
            digitized_works = DigitizedWork.objects.filter(id__in=ids)
            for collection in data['collections']:
                collection.digitizedwork_set.set(digitized_works)

            # TODO: Add solr indexing
            
            # create a success message to add to message framework stating
            # what happened
            htids = ', '.join(work.source_id for work in digitized_works)
            collections = ', '.join(collection.name for
                                    collection in data['collections'])
            messages.success(request, '%s successfully added to: %s.'
                             % (htids, collections))
        # call the super post method to trigger redirects
        # should be safe because checks form validity in either instance
        # before redirect
        return (
            super(BulkAddCollectionView, self)
            .post(self, request, *args, **kwargs)
        )
