from django.contrib import admin

from ppa.archive.models import DigitizedWork


class DigitizedWorkAdmin(admin.ModelAdmin):
    list_display = ('source_id', 'title', 'author', 'pub_place',
        'pub_date', 'page_count', 'added', 'updated')
    readonly_fields = ('source_id', 'page_count', 'added', 'updated')


admin.site.register(DigitizedWork, DigitizedWorkAdmin)

