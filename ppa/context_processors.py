from django.conf import settings
from django.contrib.sites.models import Site


def template_globals(request):
    '''Template context processor: add global includes (e.g.
    from django settings or site search form) for use on any page.'''

    context_extras = {
        'SHOW_TEST_WARNING': getattr(settings, 'SHOW_TEST_WARNING', False),
        'site': Site.objects.get_current(),
        'GTAGS_ANALYTICS_ID': getattr(settings, 'GTAGS_ANALYTICS_ID', False)
    }
    return context_extras
