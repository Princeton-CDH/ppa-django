from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse

from ppa.archive.models import DigitizedWork, Collection


class DigitizedWorkAdmin(admin.ModelAdmin):
    list_display = ('title', 'source_link', 'author', 'list_collections',
        'enumcron', 'pub_place', 'publisher', 'pub_date', 'page_count', 'notes',
        'added', 'updated')
    fields = ('source_link', 'title', 'enumcron', 'author',
        'pub_place', 'publisher', 'pub_date', 'page_count', 'collections',
        'added', 'updated')
    readonly_fields = ('source_link', 'page_count',
        'added', 'updated')
    search_fields = ('source_id', 'title', 'author', 'enumcron', 'pub_date',
        'publisher', 'notes')
    filter_horizontal = ('collections',)
    # date_hierarchy = 'added'  # is this useful?
    list_filter = ['collections']
    actions = ['bulk_add_collection']

    def list_collections(self, obj):
        '''Return a list of :class:ppa.archive.models.Collection object names
        as a comma separated list to populate a change_list column.
        '''
        return ', '.join([coll.name for coll in
                          obj.collections.all().order_by('name')])
    list_collections.short_description = 'Collections'

    def source_link(self, obj):
        return '<a href="%s" target="_blank">%s</a>' % (obj.source_url,
                                                        obj.source_id)
    source_link.short_description = 'Source id'
    source_link.admin_order_column = 'source_id'
    source_link.allow_tags = True

    def save_related(self, request, form, formsets, change):
        '''Ensure reindex is called when admin form is saved'''
        # m2m relations are handled separately by the admin form so the standard
        # save override will not help as the m2m relationship are not yet set when
        # model's save method is called. See the doc string for save_related
        # at https://docs.djangoproject.com/en/1.11/_modules/django/contrib/admin/options/#ModelAdmin.save_related

        super(DigitizedWorkAdmin, self).save_related(
            request, form, formsets, change
        )
        digwork = DigitizedWork.objects.get(id=form.instance.pk)
        digwork.index(params={"commitWithin": 10000})

    def bulk_add_collection(self, request, queryset):
        '''
        Bulk add a queryset of :class:`ppa.archive.DigitizedWork` to
        a :class:`ppa.archive.Collection`.
        '''
        # Uses POST from admin rather than a database query to get the pks
        # per the suggested practices in Django documentation
        selected = list(queryset.order_by('id').values_list('id', flat=True))
        # encode the filter querystring so that the bulk add view can return
        # the user to the same admin list view upon completion.
        request.session['collection-add-filters'] = request.GET
        request.session['collection-add-ids'] = selected
        return HttpResponseRedirect(reverse('archive:add-to-collection'))

    bulk_add_collection.short_description = ('Add selected digitized works '
                                             'to collections')


admin.site.register(DigitizedWork, DigitizedWorkAdmin)
admin.site.register(Collection)
