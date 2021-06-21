from datetime import date

from django.http import Http404
from wagtail.admin.edit_handlers import FieldPanel, StreamFieldPanel
from wagtail.core.models import Page
from wagtail.core.fields import RichTextField, StreamField
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
    content_panels = Page.content_panels + [
        FieldPanel("description"),
        StreamFieldPanel("authors"),
        StreamFieldPanel("body"),
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
            # a page without a parent is the tree root, which always has a url_path of '/'
            self.url_path = "/"

        return self.url_path
