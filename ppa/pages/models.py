from wagtail.core.models import Page
from wagtail.core.fields import RichTextField
from wagtail.admin.edit_handlers import FieldPanel

from ppa.archive.models import Collection


class HomePage(Page):
    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('body', classname="full"),
    ]


    def get_context(self, request):
        context = super().get_context(request)
        context['collections'] = Collection.objects.all().order_by('?')[:2]
        return context

