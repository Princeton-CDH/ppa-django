from django.contrib import admin

from ppa.archive.models import DigitizedWork, Collection
from ppa.common.admin import CollapsibleTabularInline


class CollectionInline(CollapsibleTabularInline):
    model = Collection.digitized_works.through
    verbose_name = 'Collection'
    verbose_name_plural = 'Collections'
    extra = 1


class DigitizedWorkAdmin(admin.ModelAdmin):
    list_display = ('source_id', 'title', 'author', 'enumcron', 'pub_place',
        'publisher', 'pub_date', 'page_count', 'added', 'updated')
    readonly_fields = ('source_id', 'source_url', 'page_count',
        'added', 'updated')
    search_fields = ('source_id', 'title', 'author', 'enumcron', 'pub_date',
        'publisher')
    inlines = [CollectionInline]
    # date_hierarchy = 'added'  # is this useful?
    # currently nothing useful to filter on; eventually will have collectio
    # list_filter = []


admin.site.register(DigitizedWork, DigitizedWorkAdmin)
admin.site.register(Collection)
