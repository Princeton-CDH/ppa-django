from django.db import models
from django.template.defaultfilters import truncatechars_html
from wagtail.core.models import Page
from wagtail.core.fields import RichTextField
from wagtail.admin.edit_handlers import FieldPanel, PageChooserPanel

from ppa.archive.models import Collection


class HomePage(Page):
    ''':class:`wagtail.core.models.Page` model for PPA home page'''
    body = RichTextField(blank=True)

    page_preview_1 = models.ForeignKey(
        'wagtailcore.Page',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text='First page to preview on the home page as a card'
    )
    page_preview_2 = models.ForeignKey(
        'wagtailcore.Page',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text='Second page to preview on the home page as card'
    )

    content_panels = Page.content_panels + [
        PageChooserPanel('page_preview_1'),
        PageChooserPanel('page_preview_2'),
        FieldPanel('body', classname="full"),
    ]

    # only generic parent page allowed, so homepage can be created under
    # Root but not otherwise used as a child page
    parent_page_types = [Page]

    class Meta:
        verbose_name = "homepage"

    def get_context(self, request):
        context = super().get_context(request)

        preview_pages = [page for page in [self.page_preview_1,
                                           self.page_preview_2] if page]

        # if no preview pages are associated, look for history and prosody
        # by slug url (preliminary urls!)
        if not preview_pages:
            preview_pages = ContentPage.objects.filter(slug__in=['history', 'prosody'])

        # grab collection page for displaying collection overview
        collection_page = CollectionPage.objects.live().first()

        # include 2 random collections
        # along with stats for all collections
        context.update({
            'collections': Collection.objects.order_by('?')[:2],
            'stats': Collection.stats(),
            'preview_pages': preview_pages,
            'collection_page': collection_page
        })
        return context


class ContentPage(Page):
    '''Basic content page model.'''
    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('body', classname="full"),
    ]

    def description(self):
        '''Brief description of the page, for use as a preview when
        displayed as a card on other pages.'''
        if self.search_description.strip():
            return self.search_description
        return truncatechars_html(self.body, 250)


class CollectionPage(Page):
    '''Collection list page, with editable text content'''
    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('body', classname="full"),
    ]

    # only allow creating directly under home page
    parent_page_types = [HomePage]
    # not allowed to have sub pages
    subpage_types = []

    def get_context(self, request):
        context = super().get_context(request)

        # include all collections with stats
        context.update({
            'collections': Collection.objects.all(),
            'stats': Collection.stats(),
        })
        return context



