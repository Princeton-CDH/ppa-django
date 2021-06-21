from django import template
from django.utils.timezone import now
from django.template.defaultfilters import stringfilter


register = template.Library()


@register.filter(is_safe=True)
@stringfilter
def format_citation(text, sw_version):
    """Simple string filter for "how to cite" page to automatically
    add current software version from the context and current date."""
    return text.replace("[SW_VERSION]", sw_version).replace(
        "[DATE]", now().strftime("%d %B %Y")
    )
