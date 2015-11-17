from django.contrib import admin, messages
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db import models as django_models
from django.forms import ModelForm, ModelMultipleChoiceField
from django.http import HttpResponseRedirect
from django.utils.translation import ungettext

from nodeconductor.core.models import SynchronizationStates, User
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


class CustomerAdminForm(ModelForm):
    owners = ModelMultipleChoiceField(User.objects.all().order_by('full_name'), required=False,
                                      widget=FilteredSelectMultiple(verbose_name='Owners', is_stacked=False))

    def __init__(self, *args, **kwargs):
        super(CustomerAdminForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.owners = self.instance.roles.get(
                role_type=models.CustomerRole.OWNER).permission_group.user_set.all()
            self.fields['owners'].initial = self.owners
        else:
            self.owners = User.objects.none()

    def save(self, commit=True):
        customer = super(CustomerAdminForm, self).save(commit=False)

        if not customer.pk:
            customer.save()

        new_owners = self.cleaned_data['owners']
        added_owners = new_owners.exclude(pk__in=self.owners)
        removed_owners = self.owners.exclude(pk__in=new_owners)
        for user in added_owners:
            customer.add_user(user, role_type=models.CustomerRole.OWNER)

        for user in removed_owners:
            customer.remove_user(user, role_type=models.CustomerRole.OWNER)

        self.save_m2m()

        return customer


class CustomerAdmin(ProtectedModelMixin, admin.ModelAdmin):
    form = CustomerAdminForm
    fields = ('name', 'image', 'native_name', 'abbreviation', 'contact_details', 'registration_code',
              'billing_backend_id', 'balance', 'owners')
    readonly_fields = ['balance']
    actions = [
        'sync_with_backend',
        'update_projected_estimate',
    ]
    list_display = ['name', 'billing_backend_id', 'uuid', 'abbreviation', 'created']

    def sync_with_backend(self, request, queryset):
        customer_uuids = list(queryset.values_list('uuid', flat=True))
        send_task('billing', 'sync_billing_customers')(customer_uuids)

        tasks_scheduled = queryset.count()
        message = ungettext(
            'One customer scheduled for sync with billing backend',
            '%(tasks_scheduled)d customers scheduled for sync with billing backend',
            tasks_scheduled
        )
        message = message % {'tasks_scheduled': tasks_scheduled}

        self.message_user(request, message)

    sync_with_backend.short_description = "Sync selected customers with billing backend"

    def update_projected_estimate(self, request, queryset):
        customers_without_backend_id = []
        succeeded_customers = []
        for customer in queryset:
            if not customer.billing_backend_id:
                customers_without_backend_id.append(customer)
                continue
            send_task('cost_tracking', 'update_projected_estimate')(
                customer_uuid=customer.uuid.hex)
            succeeded_customers.append(customer)

        if succeeded_customers:
            message = ungettext(
                'Projected estimate generation successfully scheduled for customer %(customers_names)s',
                'Projected estimate generation successfully scheduled for customers: %(customers_names)s',
                len(succeeded_customers)
            )
            message = message % {'customers_names': ', '.join([c.name for c in succeeded_customers])}
            self.message_user(request, message)

        if customers_without_backend_id:
            message = ungettext(
                'Cannot generate estimate for customer without backend id: %(customers_names)s',
                'Cannot generate estimate for customers without backend id: %(customers_names)s',
                len(customers_without_backend_id)
            )
            message = message % {'customers_names': ', '.join([c.name for c in customers_without_backend_id])}
            self.message_user(request, message)

    update_projected_estimate.short_description = "Update projected cost estimate"


class ProjectAdminForm(ModelForm):
    admins = ModelMultipleChoiceField(User.objects.all().order_by('full_name'), required=False,
                                      widget=FilteredSelectMultiple(verbose_name='Admins', is_stacked=False))
    managers = ModelMultipleChoiceField(User.objects.all().order_by('full_name'), required=False,
                                        widget=FilteredSelectMultiple(verbose_name='Managers', is_stacked=False))

    def __init__(self, *args, **kwargs):
        super(ProjectAdminForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.admins = self.instance.roles.get(
                role_type=models.ProjectRole.ADMINISTRATOR).permission_group.user_set.all()
            self.managers = self.instance.roles.get(
                role_type=models.ProjectRole.MANAGER).permission_group.user_set.all()
            self.fields['admins'].initial = self.admins
            self.fields['managers'].initial = self.managers
        else:
            self.admins, self.managers = User.objects.none(), User.objects.none()

    def save(self, commit=True):
        project = super(ProjectAdminForm, self).save(commit=False)

        if not project.pk:
            project.save()

        new_admins = self.cleaned_data['admins']
        added_admins = new_admins.exclude(pk__in=self.admins)
        removed_admins = self.admins.exclude(pk__in=new_admins)
        for user in added_admins:
            project.add_user(user, role_type=models.ProjectRole.ADMINISTRATOR)

        for user in removed_admins:
            project.remove_user(user, role_type=models.ProjectRole.ADMINISTRATOR)

        new_managers = self.cleaned_data['managers']
        added_managers = new_managers.exclude(pk__in=self.managers)
        removed_managers = self.managers.exclude(pk__in=new_managers)
        for user in added_managers:
            project.add_user(user, role_type=models.ProjectRole.MANAGER)

        for user in removed_managers:
            project.remove_user(user, role_type=models.ProjectRole.MANAGER)

        self.save_m2m()

        return project


class ProjectAdmin(ProtectedModelMixin, ChangeReadonlyMixin, admin.ModelAdmin):
    form = ProjectAdminForm

    fields = ('name', 'description', 'customer', 'admins', 'managers')

    list_display = ['name', 'uuid', 'customer', 'created']
    search_fields = ['name', 'uuid']
    change_readonly_fields = ['customer']
    inlines = [QuotaInline]


class ProjectGroupAdminForm(ModelForm):
    managers = ModelMultipleChoiceField(User.objects.all().order_by('full_name'), required=False,
                                        widget=FilteredSelectMultiple(verbose_name='Managers', is_stacked=False))

    def __init__(self, *args, **kwargs):
        super(ProjectGroupAdminForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.managers = self.instance.roles.get(
                role_type=models.ProjectGroupRole.MANAGER).permission_group.user_set.all()
            self.fields['managers'].initial = self.managers
        else:
            self.managers = User.objects.none()

    def save(self, commit=True):
        group = super(ProjectGroupAdminForm, self).save(commit=False)

        if not group.pk:
            group.save()

        new_managers = self.cleaned_data['managers']
        added_managers = new_managers.exclude(pk__in=self.managers)
        removed_managers = self.managers.exclude(pk__in=new_managers)
        for user in added_managers:
            group.add_user(user, role_type=models.ProjectGroupRole.MANAGER)

        for user in removed_managers:
            group.remove_user(user, role_type=models.ProjectGroupRole.MANAGER)

        self.save_m2m()

        return group


class ProjectGroupAdmin(ProtectedModelMixin, ChangeReadonlyMixin, admin.ModelAdmin):
    form = ProjectGroupAdminForm
    fields = ('name', 'description', 'customer', 'managers')

    list_display = ['name', 'uuid', 'customer', 'created']
    search_fields = ['name', 'uuid']
    change_readonly_fields = ['customer']


class ServiceSettingsAdmin(ChangeReadonlyMixin, admin.ModelAdmin):
    readonly_fields = ('error_message',)
    list_display = ('name', 'customer', 'type', 'shared', 'state', 'error_message')
    list_filter = ('type', 'state', 'shared')
    change_readonly_fields = ('shared', 'customer')
    actions = ['sync']

    def add_view(self, *args, **kwargs):
        self.exclude = getattr(self, 'add_exclude', ())
        return super(ServiceSettingsAdmin, self).add_view(*args, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        fields = super(ServiceSettingsAdmin, self).get_readonly_fields(request, obj)
        if obj and not obj.shared:
            if request.method == 'GET':
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


class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'customer', 'settings')
    ordering = ('name', 'customer')


class ServiceProjectLinkAdmin(admin.ModelAdmin):
    readonly_fields = ('service', 'project', 'error_message')
    list_display = ('get_service_name', 'get_customer_name', 'get_project_name', 'state')
    ordering = ('service__customer__name', 'project__name', 'service__name')
    list_display_links = ('get_service_name',)
    search_fields = ('service__customer__name', 'project__name', 'service__name')

    actions = ['sync_with_backend', 'recover_erred_service_project_links']

    def get_queryset(self, request):
        queryset = super(ServiceProjectLinkAdmin, self).get_queryset(request)
        return queryset.select_related('service', 'project', 'project__customer')

    def sync_with_backend(self, request, queryset):
        queryset = queryset.filter(state=SynchronizationStates.IN_SYNC)
        send_task('structure', 'sync_service_project_links')([spl.to_string() for spl in queryset])

        tasks_scheduled = queryset.count()
        message = ungettext(
            'One service project link scheduled for update',
            '%(tasks_scheduled)d service project links scheduled for update',
            tasks_scheduled
        )
        message = message % {'tasks_scheduled': tasks_scheduled}

        self.message_user(request, message)

    sync_with_backend.short_description = "Sync selected service project links with backend"

    def recover_erred_service_project_links(self, request, queryset):
        queryset = queryset.filter(state=SynchronizationStates.ERRED)
        send_task('structure', 'recover_erred_services')([spl.to_string() for spl in queryset])
        tasks_scheduled = queryset.count()

        message = ungettext(
            'One service project link scheduled for recovery',
            '%(tasks_scheduled)d service project links scheduled for recovery',
            tasks_scheduled
        )
        message = message % {'tasks_scheduled': tasks_scheduled}

        self.message_user(request, message)

    recover_erred_service_project_links.short_description = "Recover selected service project links"

    def get_service_name(self, obj):
        return obj.service.name

    get_service_name.short_description = 'Service'

    def get_project_name(self, obj):
        return obj.project.name

    get_project_name.short_description = 'Project'

    def get_customer_name(self, obj):
        return obj.service.customer.name

    get_customer_name.short_description = 'Customer'


class ResourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'backend_id', 'state')
    list_filter = ('state',)


admin.site.register(models.Customer, CustomerAdmin)
admin.site.register(models.Project, ProjectAdmin)
admin.site.register(models.ProjectGroup, ProjectGroupAdmin)
admin.site.register(models.ServiceSettings, ServiceSettingsAdmin)
