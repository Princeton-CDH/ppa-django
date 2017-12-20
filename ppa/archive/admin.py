from dal import autocomplete

from django.contrib import admin
from django import forms

from ppa.archive.models import DigitizedWork, Collection
from ppa.common.admin import CollapsibleTabularInline


class CollectionInline(CollapsibleTabularInline):
    model = Collection.digitized_works.through
    verbose_name = 'Collection'
    verbose_name_plural = 'Collections'
    extra = 1


class CollectionAdminForm(forms.ModelForm):
    '''Form to add autocomplete for usability on creation for
    :class:~ppa.archive.models.Collection'''
    class Meta:
        model = Collection
        fields = ('__all__')
        widgets = {
            'digitized_works': autocomplete.ModelSelect2Multiple(
                url='archive:digitizedwork-autocomplete',
                attrs={
                    'data-placeholder': 'Start typing to autocomplete...',
                    'data-minimum-input-length': 3,
                    'data-html': True,
                }
            )
        }


class CollectionAdmin(admin.ModelAdmin):
    form = CollectionAdminForm


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
admin.site.register(Collection, CollectionAdmin)
