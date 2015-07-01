from django.contrib import admin, messages
from django.core.management import call_command, CommandError
from django.db import models as django_models
from django.db.models import get_models
from django.http import HttpResponseRedirect
from django.utils.translation import ungettext
from polymorphic.admin import (
    PolymorphicParentModelAdmin, PolymorphicChildModelAdmin,
    PolymorphicChildModelFilter)

from nodeconductor.core.admin import ReversionAdmin
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.core.tasks import send_task
from nodeconductor.quotas.admin import QuotaInline
from nodeconductor.structure import models


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


class CustomerAdmin(ProtectedModelMixin, ReversionAdmin):
    readonly_fields = ['balance']
    actions = ['sync_with_backend', 'create_invoices']
    list_display = ['name', 'billing_backend_id', 'uuid', 'abbreviation']

    def sync_with_backend(self, request, queryset):
        customer_uuids = list(queryset.values_list('uuid', flat=True))
        send_task('structure', 'sync_billing_customers')(customer_uuids)

        tasks_scheduled = queryset.count()
        message = ungettext(
            'One customer scheduled for sync with billing backend',
            '%(tasks_scheduled)d customers scheduled for sync with billing backend',
            tasks_scheduled
        )
        message = message % {'tasks_scheduled': tasks_scheduled}

        self.message_user(request, message)

    sync_with_backend.short_description = "Sync selected customers with billing backend"

    def create_invoices(self, request, queryset):
        succeeded_customers = []
        for customer in queryset.iterator():
            try:
                call_command('createinvoices', customer_uuid=customer.uuid.hex)
                succeeded_customers.append(customer)
            except CommandError as e:
                message = 'Invoices creation fails for customer {} with error: {}'.format(customer.name, e.message)
                self.message_user(request, message, messages.ERROR)

        if succeeded_customers:
            message = ungettext(
                'Invoice creation successfully scheduled for customer %(customers_names)s',
                'Invoices creation successfully scheduled for customers: %(customers_names)s',
                len(succeeded_customers)
            )
            message = message % {'customers_names': ', '.join([c.name for c in succeeded_customers])}
            self.message_user(request, message)

    create_invoices.short_description = "Create invoices for last month"


class ProjectAdmin(ProtectedModelMixin, ChangeReadonlyMixin, ReversionAdmin):

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


class ServiceSettingsAdmin(ChangeReadonlyMixin, admin.ModelAdmin):
    list_display = ('name', 'customer', 'type', 'shared', 'state')
    list_filter = ('type', 'state', 'shared')
    change_readonly_fields = ('shared', 'customer')
    actions = ['sync']

    def add_view(self, *args, **kwargs):
        self.exclude = getattr(self, 'add_exclude', ())
        return super(ServiceSettingsAdmin, self).add_view(*args, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        fields = super(ServiceSettingsAdmin, self).get_readonly_fields(request, obj)
        if obj and not obj.shared:
            obj.password = '(hidden)'
            return fields + ('password',)
        return fields

    def get_form(self, request, obj=None, **kwargs):
        # filter out certain fields from the creation form
        if not obj:
            kwargs['exclude'] = ('state',)
        form = super(ServiceSettingsAdmin, self).get_form(request, obj, **kwargs)
        if 'shared' in form.base_fields:
            form.base_fields['shared'].initial = True
        return form

    def save_model(self, request, obj, form, change):
        super(ServiceSettingsAdmin, self).save_model(request, obj, form, change)
        if not change:
            send_task('structure', 'sync_service_settings')(obj.uuid.hex, initial=True)

    def sync(self, request, queryset):
        queryset = queryset.filter(state=SynchronizationStates.IN_SYNC)
        service_uuids = list(queryset.values_list('uuid', flat=True))
        tasks_scheduled = queryset.count()

        send_task('structure', 'sync_service_settings')(service_uuids)

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
