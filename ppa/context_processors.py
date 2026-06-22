from django.conf import settings
from django.contrib.sites.models import Site


def template_globals(request):
    """Template context processor: add global includes (e.g.
    from django settings or site search form) for use on any page."""

    context_extras = {
        "SHOW_TEST_WARNING": getattr(settings, "SHOW_TEST_WARNING", False),
        "site": Site.objects.get_current(),
        "GTAGS_ANALYTICS_ID": getattr(settings, "GTAGS_ANALYTICS_ID", False),
        "INCLUDE_ANALYTICS": getattr(settings, "INCLUDE_ANALYTICS", False),
        "PLAUSIBLE_ANALYTICS_SCRIPT": getattr(settings, "PLAUSIBLE_ANALYTICS_SCRIPT", False),
        "PLAUSIBLE_ANALYTICS_404s": getattr(settings, "PLAUSIBLE_ANALYTICS_404s", False),
    }
    return context_extras


def adapter_context(request):
    """Add adapter configuration to template context."""
    from ppa.adapters.loader import get_adapter

    try:
        adapter = get_adapter()
        return {
            "adapter": adapter,
            "adapter_display_fields": adapter.display_fields if adapter else None,
            "adapter_frontend": adapter.frontend if adapter else None,
        }
    except Exception:
        return {"adapter": None, "adapter_display_fields": None, "adapter_frontend": None}
