from django.utils.cache import patch_vary_headers
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
