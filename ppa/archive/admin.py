
from django.contrib import admin

from ppa.archive.models import DigitizedWork, Collection


class DigitizedWorkAdmin(admin.ModelAdmin):
    list_display = ('source_id', 'title', 'author', 'enumcron', 'pub_place',
        'publisher', 'pub_date', 'page_count', 'added', 'updated')
    readonly_fields = ('source_id', 'source_url', 'page_count',
        'added', 'updated')
    search_fields = ('source_id', 'title', 'author', 'enumcron', 'pub_date',
        'publisher')
    # date_hierarchy = 'added'  # is this useful?
    # currently nothing useful to filter on; eventually will have collectio
    # list_filter = []


admin.site.register(DigitizedWork, DigitizedWorkAdmin)
