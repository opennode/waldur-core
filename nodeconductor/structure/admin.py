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


class ServiceAdmin(PolymorphicParentModelAdmin):
    list_display = ('name', 'customer', 'polymorphic_ctype', 'state')
    ordering = ('name', 'customer')
    actions = ['sync_services']
    list_filter = (PolymorphicChildModelFilter,)
    base_model = models.Service

    def get_child_models(self):
        class BaseAdminClass(PolymorphicChildModelAdmin):
            base_model = models.Service

        return [(model, BaseAdminClass) for model in get_models()
                if model is not models.Service and issubclass(model, models.Service)]

    def sync_services(self, request, queryset):
        queryset = queryset.filter(state=SynchronizationStates.IN_SYNC)
        service_uuids = list(queryset.values_list('uuid', flat=True))
        tasks_scheduled = queryset.count()

        tasks.sync_services.delay(service_uuids)

        message = ungettext(
            'One service scheduled for sync',
            '%(tasks_scheduled)d services scheduled for sync',
            tasks_scheduled)
        message = message % {'tasks_scheduled': tasks_scheduled}

        self.message_user(request, message)

    sync_services.short_description = "Sync selected services with backend"


class HiddenServiceAdmin(admin.ModelAdmin):
    def get_model_perms(self, request):
        return {}


admin.site.register(models.Customer, CustomerAdmin)
admin.site.register(models.Project, ProjectAdmin)
admin.site.register(models.ProjectGroup, ProjectGroupAdmin)
admin.site.register(models.Service, ServiceAdmin)
