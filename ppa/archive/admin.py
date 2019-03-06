from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.safestring import mark_safe

from ppa.archive.models import DigitizedWork, Collection, \
    ProtectedWorkFieldFlags


class DigitizedWorkAdmin(admin.ModelAdmin):
    list_display = (
        'display_title', 'subtitle', 'source_link', 'record_id', 'author',
        'list_collections', 'enumcron', 'pub_place', 'publisher', 'pub_date',
        'page_count', 'is_public', 'added', 'updated'
    )
    fields = (
        'source', 'source_id', 'source_url', 'title', 'subtitle',
        'sort_title', 'enumcron', 'author', 'pub_place', 'publisher',
        'pub_date', 'page_count', 'public_notes', 'notes', 'record_id',
        'collections', 'protected_fields', 'status', 'added',
        'updated'
    )
    # fields that are always read only
    readonly_fields = (
        'added', 'updated', 'protected_fields'
    )
    # fields that are read only for HathiTrust records
    hathi_readonly_fields = (
        'source', 'source_id', 'source_url', 'page_count', 'record_id',
    )

    search_fields = (
        'source_id', 'title', 'subtitle', 'author', 'enumcron', 'pub_date',
        'publisher', 'public_notes', 'notes', 'record_id'
    )
    filter_horizontal = ('collections',)
    # date_hierarchy = 'added'  # is this useful?
    list_filter = ['collections', 'status', 'source']
    actions = ['bulk_add_collection']

    def get_readonly_fields(self, request, obj=None):
        """
        Determine read only fields based on item source, to prevent
        editing of HathiTrust fields that should not be changed.
        """
        if obj and obj.source == DigitizedWork.HATHI:
            return self.hathi_readonly_fields + self.readonly_fields
        return self.readonly_fields

    def list_collections(self, obj):
        '''Return a list of :class:ppa.archive.models.Collection object names
        as a comma separated list to populate a change_list column.
        '''
        return ', '.join([coll.name for coll in
                          obj.collections.all().order_by('name')])
    list_collections.short_description = 'Collections'

    def source_link(self, obj):
        '''Link to source record'''
        return mark_safe('<a href="%s" target="_blank">%s</a>' % \
                         (obj.source_url, obj.source_id))
    source_link.short_description = 'Source id'
    source_link.admin_order_field = 'source_id'

    def save_model(self, request, obj, form, change):
        '''Note any fields in the protected list that have been changed in
        the admin and preserve in database.'''
        # If new object, created from scratch, nothing to track and preserve
        # or if item is not a HathiTrust item, save and return
        if not change or obj.source != DigitizedWork.HATHI:
            super().save_model(request, obj, form, change)
            return
        # has_changes only works for objects that have been changed on their
        # instance -- obj is a new instance *not* a modified one,
        # so compare against database
        db_obj = DigitizedWork.objects.get(pk=obj.pk)
        changed_fields = obj.compare_protected_fields(db_obj)
        # iterate over changed fields and 'append' (OR) to flags
        for field in changed_fields:
            obj.protected_fields = obj.protected_fields | \
                ProtectedWorkFieldFlags(field)
        super().save_model(request, obj, form, change)

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


class CollectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'exclude')
    list_editable = ('exclude', )


admin.site.register(DigitizedWork, DigitizedWorkAdmin)
admin.site.register(Collection, CollectionAdmin)
