from wagtail.core.models import Page
from wagtail.core.fields import RichTextField
from wagtail.admin.edit_handlers import FieldPanel

from ppa.archive.models import Collection


class HomePage(Page):
    ''':class:`wagtail.core.models.Page` model for PPA home page'''
    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('body', classname="full"),
    ]

    # no parent page allowed (don't allow homepage to be used as a child page)
    parent_page_types = []

    class Meta:
        verbose_name = "homepage"

    def get_context(self, request):
        context = super().get_context(request)
        # include 2 random collections from those that are public
        # along withstats for all collections
        context.update({
            'collections': Collection.objects.public().order_by('?')[:2],
            'stats': Collection.stats()
        })
        return context


class ContentPage(Page):
    '''Basic content page model.'''
    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('body', classname="full"),
    ]

