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
        # TODO: need to adapt CollectionListView logic
        # to get collection stats
        context = super().get_context(request)
        context['collections'] = Collection.objects.all().order_by('?')[:2]
        return context


class ContentPage(Page):
    '''Basic content page model.'''
    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('body', classname="full"),
    ]

