from django.contrib import admin

from ppa.archive.models import DigitizedWork


class DigitizedWorkAdmin(admin.ModelAdmin):
    list_display = ('source_id', 'title', 'author', 'enumcron', 'pub_place',
        'pub_date', 'page_count', 'added', 'updated')
    readonly_fields = ('source_id', 'page_count', 'added', 'updated')
    search_fields = ('source_id', 'title', 'author', 'enumcron', 'pub_date')
    # date_hierarchy = 'added'  # is this useful?
    # currently nothing useful to filter on; eventually will have collectio
    # list_filter = []


admin.site.register(DigitizedWork, DigitizedWorkAdmin)

