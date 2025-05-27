from django.utils.html import format_html

from wagtail import hooks
from webpack_loader.templatetags.webpack_loader import render_bundle


@hooks.register("insert_editor_js")
def editor_js():
    """Wagtail hook to include a JS bundle in the page editor, in html script
    tags."""
    return format_html(render_bundle({}, "pdf", "js"))
