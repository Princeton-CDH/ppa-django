import logging

import requests
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.http import (
    Http404,
    HttpResponsePermanentRedirect,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.generic import DetailView, ListView
from django.views.generic.base import RedirectView, TemplateView
from django.views.generic.edit import FormView
from parasolr.django.views import SolrLastModifiedMixin

from ppa.archive.forms import (
    AddToCollectionForm,
    ImportForm,
    SearchForm,
    SearchWithinWorkForm,
)
from ppa.archive.import_util import GaleImporter, HathiImporter
from ppa.archive.models import NO_COLLECTION_LABEL, DigitizedWork, SourceNote
from ppa.archive.solr import ArchiveSearchQuerySet, PageSearchQuerySet
from ppa.common.views import AjaxTemplateMixin

logger = logging.getLogger(__name__)


class GracefulPaginator(Paginator):
    """Paginator override to gracefully handle out-of-range errors.
    Adapted from https://forum.djangoproject.com/t/23037"""

    def page(self, number):
        """Get the page by the supplied number. Reset to 1 if the supplied page is out of
        range."""
        try:
            number = self.validate_number(number)
        except (PageNotAnInteger, EmptyPage):
            number = 1
        return super().page(number)


class DigitizedWorkListView(AjaxTemplateMixin, SolrLastModifiedMixin, ListView):
    """Search and browse digitized works.  Based on Solr index
    of works and pages."""

    model = DigitizedWork
    template_name = "archive/digitizedwork_list.html"
    ajax_template_name = "archive/snippets/results_list.html"
    form_class = SearchForm
    paginate_by = 50
    paginator_class = GracefulPaginator
    #: title for metadata / preview
    meta_title = "Princeton Prosody Archive"
    #: page description for metadata/preview
    meta_description = """The Princeton Prosody Archive is a full-text
    searchable database of thousands of historical documents about the
    study of language and the study of poetry."""

    # keyword query; assume no search terms unless set
    query = None

    def get(self, *args, **kwargs):
        # a bug used to allow aggregation of multiple cluster params,
        # which is not supported; if detected, redirect to archive search
        cluster_param = self.request.GET.getlist("cluster")
        if cluster_param and len(cluster_param) > 1:
            response = HttpResponsePermanentRedirect(reverse("archive:list"))
            response.status_code = 303  # See other
            return response

        # otherwise, process response normally
        return super(DigitizedWorkListView, self).get(*args, **kwargs)

    def paginate_queryset(self, queryset, page_size):
        """Graceful paginate_queryset override to handle non-numeric inputs.
        Adapted from https://stackoverflow.com/a/61214021/394067"""
        try:
            return super().paginate_queryset(queryset, page_size)
        except Http404:
            # handle a 404, e.g. a non-numeric page number was entered
            paginator = self.get_paginator(
                queryset,
                page_size,
                orphans=self.get_paginate_orphans(),
                allow_empty_first_page=self.get_allow_empty(),
            )
            page = paginator.page(1)
            return (paginator, page, page.object_list, page.has_other_pages())

    def get_queryset(self, **kwargs):
        form_opts = self.request.GET.copy()
        # if relevance sort is requested but there is no keyword search
        # term present, clear it out and fallback to default sort
        if not self.form_class().has_keyword_query(form_opts):
            if "sort" in form_opts and form_opts["sort"] == "relevance":
                del form_opts["sort"]

        searchform_defaults = self.form_class.defaults()

        for key, val in searchform_defaults.items():
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

        solr_q = (
            ArchiveSearchQuerySet()
            .facet(*self.form.facet_fields)
            .order_by(self.form.get_solr_sort_field())
        )

        # components of query to filter digitized works
        if self.form.is_valid():
            search_opts = self.form.cleaned_data
            self.query = search_opts.get("query", None)
            collections = search_opts.get("collections", None)
            cluster_id = search_opts.get("cluster", None)

            solr_q.keyword_search(self.query)

            if cluster_id:
                # filter by group id if set
                solr_q = solr_q.within_cluster(cluster_id)

            # restrict by collection
            if collections:
                # if *all* collections are selected, there is no need to filter
                # (will return everything either way; keep the query simpler)
                if len(collections) < len(self.form.fields["collections"].choices):
                    # add quotes so solr will treat as exact phrase
                    # for multiword collection names
                    solr_q.work_filter(
                        collections_exact__in=['"%s"' % c for c in collections]
                    )

            # For collection exclusion logic to work properly, if no
            # collections are selected, no items should be returned.
            # This query should return no items but still provide facet
            # data to populate the collection filters on the form properly.
            else:
                solr_q.work_filter(collections_exact__exists=False)

            # filter books by title or author if there are search terms
            solr_q.work_title_search(search_opts.get("title", None))
            solr_q.work_filter(author=search_opts.get("author", None))

        for range_facet in self.form.range_facets:
            # range filter requested in search options
            start = end = None
            # if start or end is specified on the form, add a filter query
            if range_facet in search_opts and search_opts[range_facet]:
                start, end = search_opts[range_facet].split("-")
                # find works restricted by range
                solr_q.work_filter(**{"%s__range" % range_facet: (start, end)})

            # get minimum and maximum pub date values from the db
            pubmin, pubmax = self.form.pub_date_minmax()

            # NOTE: hard-coded values are fallback logic for when
            # no contents are in the database and pubmin/pubmax are None
            start = int(start) if start else pubmin or 0
            end = int(end) if end else pubmax or 1922

            # Configure range facet options specific to current field, to
            # support more than one range facet (even though not currently needed)
            # NOTE: per facet.range.include documentation, default behavior
            # is to include lower bound and exclude upper bound.
            # For simplicity, increase range end by one.
            # Calculate gap based start and end & desired number of slices
            # ideally, generate 24 slices; minimum gap size of 1
            # Use hardend to restrict last range to *actual* maximum value
            solr_q = solr_q.facet_range(
                range_facet,
                start=start,
                end=end + 1,
                gap=max(1, int((end - start) / 24)),
                hardend=True,
            )

        self.solrq = solr_q
        return solr_q

    def get_pages(self, solrq):
        """If there is a keyword search, query Solr for matching pages
        with text highlighting.
        NOTE: This has to be done as a separate query because Solr
        doesn't support highlighting on collapsed items."""

        if not self.query or not solrq.count():
            # if there is no keyword query, bail out
            return ({}, {})

        # work ids in solrq; quoting to handle ark ids
        work_id_l = ['"%s"' % d["id"] for d in solrq]

        # generate a list of page ids from the grouped results
        # NOTE: can't use alias for group_id because not using aliased queryset
        # (archive search queryset doesn't work properly for this query)
        solr_pageq = (
            PageSearchQuerySet()
            .filter(group_id__in=work_id_l)
            .filter(item_type="page")
            .search(content="(%s)" % self.query)
            .group("group_id", limit=2, sort="score desc")
            .highlight("content", snippets=3, method="unified")
        )

        # get response, this will be cached for rows specified
        # NOTE: rows argument is needed until this parasolr bug is fixed
        # https://github.com/Princeton-CDH/parasolr/issues/43
        response = solr_pageq.get_response(rows=100)

        # mimics structure of previous expand/collapse page results
        # dict is: group_id -> document list with page objects
        page_groups = {g["groupValue"]: g["doclist"] for g in response.groups}

        # get the page highlights from the solr response
        # dict is: pageid -> pagehighlights
        page_highlights = solr_pageq.get_highlighting()

        return (page_groups, page_highlights)

    def get_context_data(self, **kwargs):
        # if the form is not valid, bail out
        if not self.form.is_valid():
            context = super().get_context_data(**kwargs)
            context["search_form"] = self.form
            return context

        page_groups = facet_ranges = None

        # @NOTE: Here is the logic that may need to change->

        try:
            # catch an error connecting to solr
            context = super().get_context_data(**kwargs)
            # get expanded must be called on the *paginated* solr queryset
            # in order to get the correct number and set of expanded groups
            # - get everything from the same solr queryset to avoid extra calls
            solrq = context["page_obj"].object_list

            page_groups, page_highlights = self.get_pages(solrq)

            facet_dict = solrq.get_facets()
            self.form.set_choices_from_facets(facet_dict.facet_fields)
            # needs to be inside try/catch or it will re-trigger any error
            # @NOTE/@TODO: attrdict's as_dict wasn't working here? casting now
            facet_ranges = dict(facet_dict.facet_ranges)
            # facet ranges are used for display; when sending to solr we
            # increase the end bound by one so that year is included;
            # subtract it back so display matches user entered dates
            facet_ranges["pub_date"]["end"] -= 1

        except requests.exceptions.ConnectionError:
            # override object list with an empty list that can be paginated
            # so that template display will still work properly
            self.object_list = self.solrq.none()
            context = super().get_context_data(**kwargs)
            # NOTE: this error should possibly be raised as a 500 error,
            # or an error status set on the response
            context["error"] = "Something went wrong."

        set(page_groups.keys())
        set(page_highlights.keys())
        context.update(
            {
                "search_form": self.form,
                # total and object_list provided by paginator
                "page_groups": page_groups,
                # range facet data for publication date
                "facet_ranges": facet_ranges,
                "page_highlights": page_highlights,
                # query for use template links to detail view with search
                "query": self.query,
                "NO_COLLECTION_LABEL": NO_COLLECTION_LABEL,
                "page_title": self.meta_title,
                "page_description": self.meta_description,
                # dict of source tooltip notes keyed on source label
                # (as that's what is indexed)
                "source_notes": {
                    sn.get_source_display(): sn.note for sn in SourceNote.objects.all()
                },
            }
        )
        return context


class DigitizedWorkDetailView(AjaxTemplateMixin, SolrLastModifiedMixin, DetailView):
    """Display details for a single digitized work. If a work has been
    surpressed, returns a 410 Gone response."""

    ajax_template_name = "archive/snippets/results_within_list.html"
    model = DigitizedWork
    slug_field = "source_id"
    slug_url_kwarg = "source_id"
    form_class = SearchWithinWorkForm
    paginate_by = 50
    # redirect url for a full volume converted to a single excerpt
    redirect_url = None

    def get_template_names(self):
        if self.object.status == DigitizedWork.SUPPRESSED:
            return "410.html"
        return super().get_template_names()

    def get_solr_lastmodified_filters(self):
        if hasattr(self, "object"):
            return {"id": self.object.index_id()}
        # solr last modified mixin requires a filter; we don't want to return a header
        # if we don't have an object, so return a bogus id
        return {"id": "NOTFOUND"}

    def get_queryset(self):
        # get default queryset and filter by source id
        source_qs = (
            super().get_queryset().filter(source_id=self.kwargs.get("source_id"))
        )
        start_page = self.kwargs.get("start_page")
        # if start page is specified, filter to get the correct excerpt
        if start_page:
            qs = source_qs.by_first_page_orig(start_page)
        # if start page is NOT specified, ensure we do not retrieve an excerpt
        else:
            qs = source_qs.filter(pages_orig__exact="")

        if not qs.exists():
            #  if qs is empty and start page is not set, check if there is _one_ excerpt
            # for the source id; if there is, we want to return a permanent redirect
            if not start_page and source_qs.count() == 1:
                self.redirect_url = source_qs.first().get_absolute_url()
            if start_page:
                # if qs empty and start page _is_ set, check for an old id
                # (previously excerpt ids were based on digital page range)
                digwork_oldid = source_qs.filter(
                    old_workid="%(source_id)s-p%(start_page)s" % self.kwargs
                )
                if digwork_oldid.exists():
                    self.redirect_url = digwork_oldid.first().get_absolute_url()

        # otherwise, return a 404
        return qs

    def get(self, *args, **kwargs):
        """Handle get request, with redirect logic if redirect url is set for
        a digitized work id converted to a single excerpt."""
        try:
            response = super().get(*args, **kwargs)
        except Http404:
            # if redirect url is set (i.e., tried to retrieve a non-existent
            # full work, but there is one excerpt with that source id)
            if self.redirect_url:
                return HttpResponsePermanentRedirect(self.redirect_url)
            # otherwise, let the 404 propagate
            raise

        # set status code to 410 gone for suppressed works
        if self.object.is_suppressed:
            response.status_code = 410

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        digwork = context["object"]
        # if suppressed, don't do any further processing
        if digwork.is_suppressed:
            return context

        context.update(
            {"page_title": digwork.title, "page_description": digwork.public_notes}
        )

        # pull in the query if it exists to use
        query = self.request.GET.get("query", "")
        form_opts = self.request.GET.copy()
        form = self.form_class(form_opts)
        context.update({"search_form": form, "query": query})

        # search within a volume only supported for content with full text
        if query and digwork.has_fulltext:
            # search on the specified search terms,
            # filter on digitized work source id and page type,
            # sort by page order,
            # only return fields needed for page result display,
            # configure highlighting on page text content
            solr_pageq = (
                # NOTE: Addition of an aliased queryset changes the _s keys below
                PageSearchQuerySet()
                .search(content="(%s)" % query)
                .filter(group_id='"%s"' % digwork.index_id(), item_type="page")
                .highlight("content", snippets=3, method="unified")
                .order_by("order")
            )

            try:
                paginator = GracefulPaginator(solr_pageq, per_page=self.paginate_by)
                page_num = self.request.GET.get("page", 1)
                current_page = paginator.page(page_num)
                paged_result = current_page.object_list
                # don't try to get highlights if there are no results
                highlights = (
                    paged_result.get_highlighting() if paged_result.count() else {}
                )

                context.update(
                    {
                        "search_form": form,
                        "current_results": current_page,
                        # add highlights to context
                        "page_highlights": highlights,
                    }
                )

            except requests.exceptions.ConnectionError:
                context["error"] = "Something went wrong."
        return context


class DigitizedWorkByRecordId(RedirectView):
    """Redirect from DigitizedWork record id to detail view when possible.
    If there is only one record found, redirect. If multiple are found, 404."""

    permanent = False
    query_string = False

    def get_redirect_url(self, *args, **kwargs):
        try:
            work = get_object_or_404(DigitizedWork, record_id=kwargs["record_id"])
            return work.get_absolute_url()
        except MultipleObjectsReturned:
            raise Http404


class AddToCollection(PermissionRequiredMixin, ListView, FormView):
    """
    View to bulk add a queryset of :class:`ppa.archive.models.DigitizedWork`
    to a set of :class:`ppa.archive.models.Collection instances`.
    """

    permission_required = "archive.change_digitizedwork"
    model = DigitizedWork
    template_name = "archive/add_to_collection.html"
    form_class = AddToCollectionForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Add Digitized Works to Collections"
        context["page_title"] = "Add Digitized Works to Collections"
        return context

    def get_success_url(self):
        """
        Redirect to the :class:`ppa.archive.models.DigitizedWork`
        change_list in the Django admin with pagination and filters preserved.
        Expects :meth:`ppa.archive.admin.add_works_to_collection`
        to have set 'collection-add-filters' as a dict in the request's
        session.
        """
        change_list = reverse("admin:archive_digitizedwork_changelist")
        # get request.session's querystring filter, and if it exists
        # use it to set the querystring
        querystring = ""
        filter_dict = self.request.session.get("collection-add-filters", None)
        if filter_dict:
            querystring = "?%s" % urlencode(filter_dict)
        return "%s%s" % (change_list, querystring)

    def get_queryset(self, *args, **kwargs):
        """Return a queryset filtered by id, or empty list if no ids"""
        # get ids from session if there are any
        ids = self.request.session.get("collection-add-ids", [])
        # if somehow a problematic non-pk is pushed, will be ignored in filter
        digworks = DigitizedWork.objects.filter(id__in=ids if ids else []).order_by(
            "id"
        )
        # revise the stored list in session to eliminate any pks
        # that don't exist
        self.request.session["collection-add-ids"] = list(
            digworks.values_list("id", flat=True)
        )
        return digworks

    def post(self, request, *args, **kwargs):
        """
        Add :class:`ppa.archive.models.DigitizedWork` instances passed in form
        data to selected instances of :class:`ppa.archive.models.Collection`,
        then return to change_list view.

        Expects a list of DigitizedWork ids to be set in the request session.

        """
        form = AddToCollectionForm(request.POST)
        if form.is_valid() and request.session["collection-add-ids"]:
            data = form.cleaned_data
            # get digitzed works from validated form
            digitized_works = self.get_queryset()
            del request.session["collection-add-ids"]
            for collection in data["collections"]:
                # add rather than set to ensure add does not replace
                # previous digitized works in set.
                collection.digitizedwork_set.add(*digitized_works)
            # reindex solr with the new collection data
            DigitizedWork.index_items(digitized_works)

            # create a success message to add to message framework stating
            # what happened
            num_works = digitized_works.count()
            collections = ", ".join(
                collection.name for collection in data["collections"]
            )
            messages.success(
                request,
                "Successfully added %d works to: %s." % (num_works, collections),
            )
            # redirect to the change list with the message intact
            return redirect(self.get_success_url())
        # make form error more descriptive, default to an error re: pks
        if "collections" in form.errors:
            del form.errors["collections"]
            form.add_error(
                "collections", ValidationError("Please select at least one Collection")
            )
        # Provide an object list for ListView and emulate CBV calling
        # render_to_response to pass form with errors; just calling super
        # doesn't pass the form with error set
        self.object_list = self.get_queryset()
        return self.render_to_response(self.get_context_data(form=form))


class ImportView(PermissionRequiredMixin, FormView):
    """Admin view to import new records from sources that support
    import (HathiTrust, Gale) by providing a list of ids."""

    permission_required = "archive.add_digitizedwork"
    template_name = "archive/import.html"
    form_class = ImportForm
    page_title = "Import new records"
    import_mode = None

    def get_context_data(self, *args, **kwargs):
        # Add page title to template context data
        context = super().get_context_data(*args, **kwargs)
        context.update(
            {
                "page_title": self.page_title,
                "title": self.page_title,  # html head title
                "import_mode": self.import_mode,
            }
        )
        return context

    def form_valid(self, form):
        # Process valid form data; should return an HttpResponse.

        source_ids = form.get_source_ids()
        source = form.cleaned_data["source"]

        # set readable import mode for display in template
        self.import_mode = dict(form.fields["source"].choices)[source]

        # initialize appropriate importer class according to source
        if source == DigitizedWork.HATHI:
            importer_class = HathiImporter
        elif source == DigitizedWork.GALE:
            importer_class = GaleImporter
        importer = importer_class(source_ids)

        # import the records and report
        return self.import_records(importer)

    def import_records(self, importer):
        """Import records based on values submitted in the form"""
        importer.filter_existing_ids()
        # add items, and create log entries associated with current user
        importer.add_items(log_msg_src="via django admin", user=self.request.user)
        importer.index()

        # generate lookup for admin urls keyed on source id to simplify
        # template logic needed
        admin_urls = {
            htid: reverse("admin:archive_digitizedwork_change", args=[pk])
            for htid, pk in importer.existing_ids.items()
        }
        for work in importer.imported_works:
            admin_urls[work.source_id] = reverse(
                "admin:archive_digitizedwork_change", args=[work.pk]
            )

        # Default form_valid behavior is to redirect to success url,
        # but we actually want to redisplay the template with results
        # and allow submitting the form again with a new batch.
        return render(
            self.request,
            self.template_name,
            context={
                "results": importer.output_results(),
                "existing_ids": importer.existing_ids,
                "form": self.form_class(),  # new form instance
                "page_title": self.page_title,
                "title": self.page_title,
                "admin_urls": admin_urls,
                "import_mode": self.import_mode,  # readable version of hathi/gale
            },
        )


class OpenSearchDescriptionView(TemplateView):
    """Basic open search description for searching the archive
    via browser or other tools."""

    template_name = "archive/opensearch_description.xml"
    content_type = "application/opensearchdescription+xml"
