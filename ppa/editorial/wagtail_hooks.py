from django.utils.html import format_html

from wagtail import hooks
from wagtail.admin.panels import FieldPanel
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet
from taggit.models import Tag
from webpack_loader.templatetags.webpack_loader import render_bundle


@hooks.register("insert_editor_js")
def editor_js():
    """Wagtail hook to include a JS bundle in the page editor, in html script
    tags."""
    return format_html(render_bundle({}, "pdf", "js"))


@register_snippet
class TagsSnippetViewSet(SnippetViewSet):
    """
    Tag management admin interface, adapted from
    https://docs.wagtail.org/en/v7.0.1/advanced_topics/tags.html#managing-tags-as-snippets
    """

    panels = [FieldPanel("name")]
    model = Tag
    icon = "tag"
    add_to_admin_menu = True
    menu_label = "Tags"
    menu_order = 400
    list_display = ["name", "slug"]
    search_fields = ("name",)
