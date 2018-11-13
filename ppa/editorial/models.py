from django.db import models
from wagtail.core import blocks
from wagtail.core.models import Page
from wagtail.core.fields import RichTextField, StreamField
from wagtail.admin.edit_handlers import FieldPanel, StreamFieldPanel
from wagtail.images.blocks import ImageChooserBlock
from wagtail.documents.blocks import DocumentChooserBlock


class EditorialIndexPage(Page):
    '''Editorial index page; list recent editorial articles.'''
    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('intro', classname="full")
    ]

    # can only be created under home page; can only have
    # editorial pages as subpages
    parent_page_types = ['pages.HomePage']
    subpage_types = ['editorial.EditorialPage']

    def get_context(self, request):
        context = super().get_context(request)

        # Add extra variables and return the updated context
        context['posts'] = EditorialPage.objects.child_of(self).live()
        return context


class EditorialPage(Page):
    '''Editorial page, for scholarly, educational, or other essay-like
    content related to the site'''

    # TODO
    # post date - default to today? or date published?
    # need person chooser - allow multiple authors, ordered author

    date = models.DateField("Post date")
    # preliminary streamfield; we may need other options for content
    # (maybe a footnotes block?)
    body = StreamField([
        ('paragraph', blocks.RichTextBlock()),
        ('image', ImageChooserBlock()),
        ('document', DocumentChooserBlock()),
    ])
    content_panels = Page.content_panels + [
        FieldPanel('date'),
        StreamFieldPanel('body'),
    ]

    # can only be under editorial, cannot have subpages
    parent_page_types = ['editorial.EditorialIndexPage']
    subpage_types = []
