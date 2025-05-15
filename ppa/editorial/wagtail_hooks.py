from django.utils.html import format_html

from wagtail import hooks
from webpack_loader.templatetags.webpack_loader import render_bundle


@hooks.register("insert_editor_js")
def editor_js():
    return format_html(render_bundle({}, "pdf", "js"))
