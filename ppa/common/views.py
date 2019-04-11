import calendar
from datetime import datetime

from django.utils.cache import get_conditional_response, patch_vary_headers
from django.views.generic.base import View, TemplateResponseMixin


class VaryOnHeadersMixin(View):
    '''View mixin to set Vary header - class-based view equivalent to
    :meth:`django.views.decorators.vary.vary_on_headers`, adapted from
    winthrop-django.

    Define :attr:`vary_headers` with the list of headers.
    '''

    vary_headers = []

    def dispatch(self, request, *args, **kwargs):
        '''Wrap default dispatch method to patch haeders on the response.'''
        response = super(VaryOnHeadersMixin, self).dispatch(request, *args, **kwargs)
        patch_vary_headers(response, self.vary_headers)
        return response


class AjaxTemplateMixin(TemplateResponseMixin, VaryOnHeadersMixin):
    '''View mixin to use a different template when responding to an ajax
    request.'''

    #: name of the template to use for ajax request
    ajax_template_name = None
    #: vary on X-Request-With to avoid browsers caching and displaying
    #: ajax response for the non-ajax response
    vary_headers = ['X-Requested-With']

    def get_template_names(self):
        '''Return :attr:`ajax_template_name` if this is an ajax request;
        otherwise return default template name.'''
        if self.request.is_ajax():
            return self.ajax_template_name
        return super().get_template_names()


# last modified view mixins borrowed from winthrop

class LastModifiedMixin(View):
    """View mixin to add last modified headers"""

    def last_modified(self):
        # for single-object displayable
        return self.get_object().updated

    def dispatch(self, request, *args, **kwargs):
        # NOTE: this doesn't actually skip view processing,
        # but without it we could return a not modified for a non-200 response
        response = super(LastModifiedMixin, self).dispatch(request, *args, **kwargs)

        last_modified = self.last_modified()
        if last_modified:
            # remove microseconds so that comparison will pass,
            # since microseconds are not included in the last-modified header
            last_modified = self.last_modified().replace(microsecond=0)
            response['Last-Modified'] = last_modified.strftime('%a, %d %b %Y %H:%M:%S GMT')
            # convert the same way django does so that they will
            # compare correctly
            last_modified = calendar.timegm(last_modified.utctimetuple())

        return get_conditional_response(request, last_modified=last_modified,
                                        response=response)

    @staticmethod
    def solr_timestamp_to_datetime(solr_time):
        """Convert Solr timestamp (isoformat that may or may not include
        microseconds) to :class:`datetime.datetime`"""
        # Solr stores date in isoformat; convert to datetime object
        # - microseconds only included when second is not exact; strip out if
        #    they are present
        if '.' in solr_time:
            solr_time = '%sZ' % solr_time.split('.')[0]
        return datetime.strptime(solr_time, '%Y-%m-%dT%H:%M:%SZ')


class LastModifiedListMixin(LastModifiedMixin):
    """Variant of :class:`LastModifiedMixin` for use on a list view"""

    def last_modified(self):
        # for list object displayable; assumes django queryset
        queryset = self.get_queryset()
        if queryset.exists():
            return queryset.order_by('updated').first().updated
