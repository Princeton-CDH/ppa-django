from django.db import models
from django.template.defaultfilters import truncatechars_html, striptags
from wagtail.core import blocks
from wagtail.core.models import Page
from wagtail.core.fields import RichTextField, StreamField
from wagtail.admin.edit_handlers import FieldPanel, PageChooserPanel, \
    StreamFieldPanel
from wagtail.images.blocks import ImageChooserBlock
from wagtail.documents.blocks import DocumentChooserBlock

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


class BodyContentBlock(blocks.StreamBlock):
    '''Common set of content blocks to be used on both content pages
    and editorial pages'''
    paragraph = blocks.RichTextBlock()
    image  =  ImageChooserBlock()
    document = DocumentChooserBlock()


class PagePreviewDescriptionMixin(models.Model):
    description = RichTextField(blank=True,
        help_text='Optional. Brief description for preview display. Will ' +
        'also be used for search description (without tags), if one is not entered.')

    class Meta:
        abstract = True

    def get_description(self):
        '''Get formatted description for preview. Uses description field
        if there is content, otherwise uses the beginning of the body content.'''
        if self.description.strip():
            return self.description

        # TODO: iterate blocks and only use the first text block (i.e. skip images)
        return truncatechars_html(self.body, 250)

    def get_plaintext_description(self):
        '''Get plain-text description for use in metadata. Uses
        search_description field if set; otherwise uses the result of
        :meth:`get_description` with tags stripped.'''

        if self.search_description.strip():
            return self.search_description
        return striptags(self.get_description())


class ContentPage(Page, PagePreviewDescriptionMixin):
    '''Basic content page model.'''
    body = StreamField(BodyContentBlock)

    content_panels = Page.content_panels + [
        FieldPanel('description'),
        StreamFieldPanel('body'),
    ]

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



