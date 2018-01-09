
from django.contrib import admin
from ppa.archive.models import DigitizedWork, Collection


class DigitizedWorkAdmin(admin.ModelAdmin):
    list_display = ('source_id', 'title', 'author', 'enumcron', 'pub_place',
        'publisher', 'pub_date', 'page_count', 'added', 'updated')
    readonly_fields = ('source_id', 'source_url', 'page_count',
        'added', 'updated')
    search_fields = ('source_id', 'title', 'author', 'enumcron', 'pub_date',
        'publisher')
    filter_horizontal = ('collections',)
    # date_hierarchy = 'added'  # is this useful?
    list_filter = ['collections']

    def save_related(self, request, form, formsets, change):
        '''Ensure reindex is called when admin form is saved'''
        # m2m relations are handled separately by the form so the standard
        # save override will not help
        super(DigitizedWorkAdmin, self).save_related(
            request, form, formsets, change
        )
        digwork = DigitizedWork.objects.get(id=form.instance.pk)
        digwork.index()


admin.site.register(DigitizedWork, DigitizedWorkAdmin)
admin.site.register(Collection)
