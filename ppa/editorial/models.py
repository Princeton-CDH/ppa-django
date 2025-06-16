from datetime import date

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.http import Http404
from django.utils.safestring import mark_safe
from modelcluster.fields import ParentalKey
from modelcluster.contrib.taggit import ClusterTaggableManager
from taggit.models import TaggedItemBase
from wagtail.admin.panels import FieldPanel, Panel
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page
from wagtail.snippets.blocks import SnippetChooserBlock

from ppa.pages.models import BodyContentBlock, PagePreviewDescriptionMixin, Person


class EditorialIndexPage(Page):
    """Editorial index page; list recent editorial articles."""

    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [FieldPanel("intro", classname="full")]

    # can only be created under home page; can only have
    # editorial pages as subpages
    parent_page_types = ["pages.HomePage"]
    subpage_types = ["editorial.EditorialPage"]

    def get_context(self, request):
        """Add published editorial posts to template context, most recent first"""
        context = super().get_context(request)

        # Add extra variables and return the updated context
        context["posts"] = (
            EditorialPage.objects.child_of(self).live().order_by("-first_published_at")
        )
        return context

    def route(self, request, path_components):
        """Customize editorial page routing to serve editorial pages
        by year/month/slug."""

        # NOTE: might be able to use RoutablePageMixin for this,
        # but could not get that to work

        if path_components:
            # if not enough path components are specified, raise a 404
            if len(path_components) < 3:
                raise Http404
                # (could eventually handle year/month to display posts by
                # date, but not yet implemented)

            # currently only handle year/month/post-slug/
            if len(path_components) >= 3:
                # request is for a child of this page

                # not using a regex route, so check character count
                # - want a four-digit year and a two-digit month
                if len(path_components[0]) != 4 or len(path_components[1]) != 2:
                    raise Http404

                try:
                    year = int(path_components[0])
                    month = int(path_components[1])
                except ValueError:
                    # if year or month are not numeric, then 404
                    raise Http404

                child_slug = path_components[2]
                remaining_components = path_components[3:]

                # find a matching child or 404
                try:
                    subpage = self.get_children().get(
                        first_published_at__year=year,
                        first_published_at__month=month,
                        slug=child_slug,
                    )
                except Page.DoesNotExist:
                    raise Http404

                # delegate further routing to child page
                return subpage.specific.route(request, remaining_components)

        else:
            # handle normally (display current page)
            return super().route(request, path_components)


@register_setting(icon="cog")
class DocraptorSettings(BaseGenericSetting):
    docraptor_api_key = models.CharField(
        "DocRaptor API key",
        max_length=255,
        blank=True,
        help_text=mark_safe(
            "API Key for DocRaptor, found on your "
            '<a href="https://docraptor.com/doc_logs">DocRaptor account page</a>. '
            "Required to enable PDF generation."
        ),
    )
    docraptor_limit_note = models.TextField(
        "DocRaptor limit note",
        default="Limited to 5 PDFs per month.",
        help_text="A note that will appear in the editor if the API key is present, "
        "informing users of the document limit. It is 5 per month on the free plan; "
        "edit here if plan is upgraded.",
    )

    panels = [
        FieldPanel("docraptor_api_key"),
        FieldPanel("docraptor_limit_note"),
    ]

    class Meta:
        verbose_name = "DocRaptor Settings"


class GeneratePdfPanel(Panel):
    """Panel for asynchronous PDF generation in JavaScript; must be a
    Panel subclass to have access to EditoralPage's instance URL"""

    class BoundPanel(Panel.BoundPanel):
        template_name = "wagtailadmin/panels/pdf_panel.html"

        def get_context_data(self, parent_context=None):
            """Override to insert live page URL and docraptor API key"""
            context = super().get_context_data(parent_context)

            # NOTE: See DEVELOPERNOTES.rst for instructions to test this in
            # development, under "Testing local DocRaptor PDF generation."
            url = self.instance.full_url

            # disable if unpublished, or has unpublished changes
            if (
                not url
                or not self.instance.live
                or self.instance.has_unpublished_changes
            ):
                url = ""
            context.update({"url": url})
            return context


class EditorialPageTag(TaggedItemBase):
    """Through model for tagging EditorialPage instances"""
    content_object = ParentalKey(
        "editorial.EditorialPage", on_delete=models.CASCADE, related_name="tagged_items"
    )


validate_doi = RegexValidator(
    regex=r"^10[.][0-9]{4,}", message="DOI in short form, starting with 10."
)


class EditorialPage(Page, PagePreviewDescriptionMixin):
    """Editorial page, for scholarly, educational, or other essay-like
    content related to the site"""

    # preliminary streamfield; we may need other options for content
    # (maybe a footnotes block?)
    body = StreamField(BodyContentBlock)
    authors = StreamField(
        [("author", SnippetChooserBlock(Person))],
        blank=True,
        help_text="Select or create people snippets to add as authors.",
    )
    editors = StreamField(
        [("editor", SnippetChooserBlock(Person))],
        blank=True,
        help_text="Select or create people snippets to add as editors.",
    )
    doi = models.CharField(
        "DOI",
        blank=True,
        max_length=255,
        help_text="Digital Object Identifier (DOI) if registered, in short form",
        validators=[validate_doi],
    )
    pdf = models.URLField(
        "PDF URL",
        blank=True,
        max_length=255,
        help_text="URL for a PDF of this article, if available",
    )
    tags = ClusterTaggableManager(through=EditorialPageTag, blank=True)
    content_panels = Page.content_panels + [
        FieldPanel("description"),
        FieldPanel("tags"),
        FieldPanel("authors"),
        FieldPanel("editors"),
        FieldPanel("doi"),
        FieldPanel("pdf"),
        GeneratePdfPanel(),  # use custom panel for PDF generation
        FieldPanel("body"),
    ]

    # can only be under editorial, cannot have subpages
    parent_page_types = ["editorial.EditorialIndexPage"]
    subpage_types = []

    def set_url_path(self, parent):
        """
        Generate the url_path field based on this page's slug, first publication date,
        and the specified parent page. Adapted from default logic to include
        publication date.
        (Parent is passed in for previewing unsaved pages)
        """
        # use current date for preview if first published is not set
        post_date = self.first_published_at or date.today()
        if parent:
            self.url_path = "{}{}/{}/".format(
                parent.url_path, post_date.strftime("%Y/%m"), self.slug
            )
        else:
            # a page without a parent is the tree root,
            # which always has a url_path of '/'
            self.url_path = "/"

        return self.url_path
