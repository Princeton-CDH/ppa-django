import json
import logging

from django.views.generic import ListView, DetailView
from SolrClient.exceptions import SolrError

from ppa.archive.forms import SearchForm
from ppa.archive.models import DigitizedWork
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
        query = join_q = None
        if self.form.is_valid():
            query = self.form.cleaned_data.get("query", "")
        if query:
            # simple keyword search across all text content
            solr_q = join_q = "text:(%s)" % query
            # use join to ensure we always get the work if any pages match
            # using query syntax as documented at
            # http://comments.gmane.org/gmane.comp.jakarta.lucene.solr.user/95646
            # to support exact phrase searches
            solr_q = 'text:(%s) OR {!join from=srcid to=id v=$join_query}' % (query)
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

        self.solrq = PagedSolrQuery({
            'q': solr_q,
            'sort': solr_sort,
            'fl': fields,
            # collapse work and pages; sort so work is first, then by page
            'fq': '{!collapse field=srcid sort="order asc"}',
            # default expand sort is score desc
            'expand': 'true',
            'expand.rows': 10,   # number of items in the collapsed group, i.e pages to display
            'join_query': join_q,
        })
        return self.solrq

    def get_context_data(self, **kwargs):
        page_groups = None
        try:
            # catch an error querying solr when the search terms cannot be parsed
            # (e.g., incomplete exact phrase)
            context = super(DigitizedWorkListView, self).get_context_data(**kwargs)
            page_groups = json.loads(self.solrq.get_json()).get('expanded', {})
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


