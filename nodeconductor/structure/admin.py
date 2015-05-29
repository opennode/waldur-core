from django.db import models as django_models
from django.db.models import get_models
from django.http import HttpResponseRedirect
from django.contrib import admin, messages
from django.utils.translation import ungettext
from polymorphic.admin import (
    PolymorphicParentModelAdmin, PolymorphicChildModelAdmin,
    PolymorphicChildModelFilter)

from nodeconductor.core.models import SynchronizationStates
from nodeconductor.quotas.admin import QuotaInline
from nodeconductor.structure import models
from nodeconductor.structure import tasks


class ChangeReadonlyMixin(object):

    add_readonly_fields = ()
    change_readonly_fields = ()

    def get_readonly_fields(self, request, obj=None):
        fields = super(ChangeReadonlyMixin, self).get_readonly_fields(request, obj)
        if hasattr(request, '_is_admin_add_view') and request._is_admin_add_view:
            return tuple(set(fields) | set(self.add_readonly_fields))
        else:
            return tuple(set(fields) | set(self.change_readonly_fields))

    def add_view(self, request, *args, **kwargs):
        request._is_admin_add_view = True
        return super(ChangeReadonlyMixin, self).add_view(request, *args, **kwargs)


class ProtectedModelMixin(object):
    def delete_view(self, request, *args, **kwargs):
        try:
            response = super(ProtectedModelMixin, self).delete_view(request, *args, **kwargs)
        except django_models.ProtectedError as e:
            self.message_user(request, e, messages.ERROR)
            return HttpResponseRedirect('.')
        else:
            return response


class CustomerAdmin(ProtectedModelMixin, admin.ModelAdmin):
    readonly_fields = ['balance']
    actions = ['sync_with_backend']

    def sync_with_backend(self, request, queryset):
        customer_uuids = list(queryset.values_list('uuid', flat=True))
        tasks.sync_billing_customers.delay(customer_uuids)

        tasks_scheduled = queryset.count()
        message = ungettext(
            'One customer scheduled for sync with billing backend',
            '%(tasks_scheduled)d customers scheduled for sync with billing backend',
            tasks_scheduled
        )
        message = message % {'tasks_scheduled': tasks_scheduled}

        self.message_user(request, message)

    sync_with_backend.short_description = "Sync selected customers with billing backend"


class ProjectAdmin(ProtectedModelMixin, ChangeReadonlyMixin, admin.ModelAdmin):

    fields = ('name', 'description', 'customer')

    list_display = ['name', 'uuid', 'customer']
    search_fields = ['name', 'uuid']
    change_readonly_fields = ['customer']
    inlines = [QuotaInline]


class ProjectGroupAdmin(ProtectedModelMixin, ChangeReadonlyMixin, admin.ModelAdmin):

    fields = ('name', 'description', 'customer')

    list_display = ['name', 'uuid', 'customer']
    search_fields = ['name', 'uuid']
    change_readonly_fields = ['customer']


class ServiceSettingsAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'state')
    list_filter = ('type',)
    actions = ['sync']

    def save_model(self, request, obj, form, change):
        super(ServiceSettingsAdmin, self).save_model(request, obj, form, change)
        if not change:
            tasks.begin_syncing_service_settings.delay(obj.uuid.hex)

    def sync(self, request, queryset):
        queryset = queryset.filter(state=SynchronizationStates.IN_SYNC)
        service_uuids = list(queryset.values_list('uuid', flat=True))
        tasks_scheduled = queryset.count()

        tasks.sync_service_settings.delay(service_uuids)

        message = ungettext(
            'One service settings record scheduled for sync',
            '%(tasks_scheduled)d service settings records scheduled for sync',
            tasks_scheduled)
        message = message % {'tasks_scheduled': tasks_scheduled}

        self.message_user(request, message)

    sync.short_description = "Sync selected service settings with backend"


class ServiceAdmin(PolymorphicParentModelAdmin):
    list_display = ('name', 'customer', 'settings', 'polymorphic_ctype')
    ordering = ('name', 'customer')
    list_filter = (PolymorphicChildModelFilter,)
    base_model = models.Service

    def get_child_models(self):
        class BaseAdminClass(PolymorphicChildModelAdmin):
            base_model = models.Service

        return [(model, BaseAdminClass) for model in get_models()
                if model is not models.Service and issubclass(model, models.Service)]


class HiddenServiceAdmin(admin.ModelAdmin):
    def get_model_perms(self, request):
        return {}


admin.site.register(models.Customer, CustomerAdmin)
admin.site.register(models.Project, ProjectAdmin)
admin.site.register(models.ProjectGroup, ProjectGroupAdmin)
admin.site.register(models.Service, ServiceAdmin)
admin.site.register(models.ServiceSettings, ServiceSettingsAdmin)
