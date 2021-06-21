from django.contrib import admin
from django.contrib.redirects.models import Redirect
from taggit.models import Tag
from wagtail.documents.models import Document
from wagtail.images.models import Image

# unregister wagtail content from django admin to avoid
# editing something in the wrong place and potentially causing
# problems

admin.site.unregister(Redirect)
admin.site.unregister(Image)
admin.site.unregister(Document)
admin.site.unregister(Tag)
