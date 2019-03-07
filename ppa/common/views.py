from django.utils.cache import patch_vary_headers
from django.views.generic.base import View


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


class AjaxTemplateMixin(VaryOnHeadersMixin):
    '''View mixin to return a different version of a view's template when
    responding to an ajax request.
    '''

    ajax_template_name = None
    vary_headers = ['X-Requested-With']

    def get_template_names(self):
        if self.request.is_ajax():
            return self.ajax_template_name
        return super().get_template_names()