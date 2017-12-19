from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

class LocalUserAdmin(UserAdmin):
    list_display = UserAdmin.list_display + ('is_superuser', 'is_active',
        'last_login', 'group_names')

    def group_names(self, obj):
        '''custom property to display group membership'''
        if obj.groups.exists():
            return ', '.join(g.name for g in obj.groups.all())
    group_names.short_description = 'groups'


class CollapsibleTabularInline(admin.TabularInline):
    '''Django admin tabular inline with grappelli collapsible classes added'''
    classes = ('grp-collapse grp-open',)


admin.site.unregister(User)
admin.site.register(User, LocalUserAdmin)
