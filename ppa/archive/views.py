import json
import logging

from django.conf import settings
from django.views.generic import TemplateView
from SolrClient import SolrClient

from ppa.archive.forms import SearchForm


logger = logging.getLogger(__name__)


class ItemListView(TemplateView):

    template_name = 'archive/list_items.html'
    # NOTE: listview would be nice, but would have to figure out how to
    # make solrclient compatible with django pagination

    def get_context_data(self, **kwargs):
        context = super(ItemListView, self).get_context_data(**kwargs)
        # todo: utility method to init solr client
        # - with maybe a wrapper that sets default
        solr_config = settings.SOLR_CONNECTIONS['default']
        solr = SolrClient(solr_config['URL'])
        solr_collection = solr_config['COLLECTION']

        form = SearchForm(self.request.GET)
        query = join_q = None
        if form.is_valid():
            query = form.cleaned_data.get("query", "")
        if query:
            # simple keyword search across all text content
            solr_q = join_q = "text:(%s)" % query
            # use join to ensure we always get the work if any pages match
            # using query syntax as documented at
            # http://comments.gmane.org/gmane.comp.jakarta.lucene.solr.user/95646
            # to support exact phrase searches
            solr_q = 'text:(%s) OR {!join from=srcid to=id v=$join_query}' % (query)
            # sort by relevance, return score for display
            sort = 'relevance'
            solr_sort = 'score desc'
            fields = '*,score'
        else:
            # no search term - find everything
            solr_q = "*:*"
            # for now, use title for default sort
            sort = 'title'
            solr_sort = 'title_exact asc'
            fields = '*'

        logger.debug("Solr search query: %s", solr_q)

        response = solr.query(solr_collection, {
            'q': solr_q,
            'sort': solr_sort,
            'fl': fields,
            # collapse work and pages; sort so work is first, then by page
            'fq': '{!collapse field=srcid sort="order asc"}',
            # default expand sort is score desc
            'expand': 'true',
            'expand.rows': 10,   # number of items in the collapsed group, i.e pages to display
            'join_query': join_q,
            'rows': 50  # override solr default of 10 results; display 50 at a time for now
        })
        context.update({
            'search_form': form,
            'total': response.get_num_found(),
            'items': response.docs,
            'sort': sort,
            'page_groups': json.loads(response.get_json())['expanded']
        })
        return context


