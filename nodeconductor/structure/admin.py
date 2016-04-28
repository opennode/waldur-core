from django.conf.urls import patterns, url
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import ValidationError
from django.db import models as django_models
from django.forms import ModelForm, ModelMultipleChoiceField, ChoiceField, RadioSelect
from django.http import HttpResponseRedirect
from django.utils import six
from django.utils.translation import ungettext
from django.shortcuts import render

from nodeconductor.core.admin import get_admin_url, ExecutorAdminAction
from nodeconductor.core.models import User
from nodeconductor.core.tasks import send_task
from nodeconductor.quotas.admin import QuotaInline
from nodeconductor.structure import models, SupportedServices, executors


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


class ResourceCounterFormMixin(object):

    def get_vm_count(self, obj):
        return obj.quotas.get(name=obj.Quotas.nc_vm_count).usage

    get_vm_count.short_description = 'VM count'

    def get_app_count(self, obj):
        return obj.quotas.get(name=obj.Quotas.nc_app_count).usage

    get_app_count.short_description = 'Application count'

    def get_private_cloud_count(self, obj):
        return obj.quotas.get(name=obj.Quotas.nc_private_cloud_count).usage

    get_private_cloud_count.short_description = 'Private cloud count'


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


class CustomerAdmin(ResourceCounterFormMixin, ProtectedModelMixin, admin.ModelAdmin):
    form = CustomerAdminForm
    fields = ('name', 'image', 'native_name', 'abbreviation', 'contact_details', 'registration_code',
              'billing_backend_id', 'balance', 'owners')
    readonly_fields = ['balance']
    actions = ['update_projected_estimate']
    list_display = ['name', 'billing_backend_id', 'uuid', 'abbreviation', 'created', 'get_vm_count', 'get_app_count', 'get_private_cloud_count']
    inlines = [QuotaInline]

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


class ProjectAdmin(ResourceCounterFormMixin, ProtectedModelMixin, ChangeReadonlyMixin, admin.ModelAdmin):
    form = ProjectAdminForm

    fields = ('name', 'description', 'customer', 'admins', 'managers')

    list_display = ['name', 'uuid', 'customer', 'created', 'get_vm_count', 'get_app_count', 'get_private_cloud_count']
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


class ServiceSettingsAdminForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(ServiceSettingsAdminForm, self).__init__(*args, **kwargs)
        self.fields['type'] = ChoiceField(choices=SupportedServices.get_choices(),
                                          widget=RadioSelect)


class ServiceTypeFilter(SimpleListFilter):
    title = 'type'
    parameter_name = 'type'

    def lookups(self, request, model_admin):
        return SupportedServices.get_choices()

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(type=self.value())
        else:
            return queryset


class ServiceSettingsAdmin(ChangeReadonlyMixin, admin.ModelAdmin):
    readonly_fields = ('error_message',)
    list_display = ('name', 'customer', 'get_type_display', 'shared', 'state', 'error_message')
    list_filter = (ServiceTypeFilter, 'state', 'shared')
    change_readonly_fields = ('shared', 'customer')
    actions = ['pull', 'connect_shared']
    form = ServiceSettingsAdminForm
    fields = ('type', 'name', 'backend_url', 'username', 'password',
              'token', 'certificate', 'options', 'customer', 'shared', 'state', 'error_message', 'tags')
    inlines = [QuotaInline]

    def get_type_display(self, obj):
        return obj.get_type_display()
    get_type_display.short_description = 'Type'

    def add_view(self, *args, **kwargs):
        self.exclude = getattr(self, 'add_exclude', ())
        return super(ServiceSettingsAdmin, self).add_view(*args, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        fields = super(ServiceSettingsAdmin, self).get_readonly_fields(request, obj)
        if obj and not obj.shared:
            if request.method == 'GET':
                obj.password = '(hidden)'
            return fields + ('password',)
        if not obj:
            return fields + ('state',)
        return fields

    def get_form(self, request, obj=None, **kwargs):
        # filter out certain fields from the creation form
        form = super(ServiceSettingsAdmin, self).get_form(request, obj, **kwargs)
        if 'shared' in form.base_fields:
            form.base_fields['shared'].initial = True
        return form

    def get_urls(self):
        my_urls = patterns(
            '',
            url(r'^(.+)/services/$', self.admin_site.admin_view(self.services)),
        )
        return my_urls + super(ServiceSettingsAdmin, self).get_urls()

    def services(self, request, pk=None):
        settings = models.ServiceSettings.objects.get(id=pk)
        projects = {}

        for name, model in SupportedServices.get_service_models().items():
            if name == SupportedServices.Types.IaaS:
                continue

            services = model['service'].objects.filter(settings=settings).values_list('id', flat=True)
            for spl in model['service_project_link'].objects.filter(service__in=services):
                projects.setdefault(spl.project.id, {
                    'name': six.text_type(spl.project),
                    'url': get_admin_url(spl.project),
                    'services': [],
                })
                projects[spl.project.id]['services'].append({
                    'name': six.text_type(spl.service),
                    'url': get_admin_url(spl.service),
                })

        return render(request, 'structure/service_settings_entities.html', {'projects': projects.values()})

    class Pull(ExecutorAdminAction):
        executor = executors.ServiceSettingsPullExecutor
        short_description = 'Pull'

        def validate(self, service_settings):
            States = models.ServiceSettings.States
            if service_settings.state not in (States.OK, States.ERRED):
                raise ValidationError('Service settings has to be OK or erred.')

    pull = Pull()

    class ConnectShared(ExecutorAdminAction):
        executor = executors.ServiceSettingsConnectSharedExecutor
        short_description = 'Create SPLs and services for shared service settings'

        def validate(self, service_settings):
            if not service_settings.shared:
                raise ValidationError('It is impossible to connect not shared settings')

    connect_shared = ConnectShared()

    def save_model(self, request, obj, form, change):
        obj.save()
        if not change:
            executors.ServiceSettingsCreateExecutor.execute(obj)


class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'customer', 'settings')
    ordering = ('name', 'customer')


class ServiceProjectLinkAdmin(admin.ModelAdmin):
    readonly_fields = ('service', 'project')
    list_display = ('get_service_name', 'get_customer_name', 'get_project_name')
    list_filter = ('service__settings', 'project__name')
    ordering = ('service__customer__name', 'project__name', 'service__name')
    list_display_links = ('get_service_name',)
    search_fields = ('service__customer__name', 'project__name', 'service__name')
    inlines = [QuotaInline]

    def get_queryset(self, request):
        queryset = super(ServiceProjectLinkAdmin, self).get_queryset(request)
        return queryset.select_related('service', 'project', 'project__customer')

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
    readonly_fields = ('error_message',)
    list_display = ('name', 'backend_id', 'state', 'get_service', 'get_project', 'error_message')
    list_filter = ('state',)

    def get_service(self, obj):
        return obj.service_project_link.service

    get_service.short_description = 'Service'
    get_service.admin_order_field = 'service_project_link__service__name'

    def get_project(self, obj):
        return obj.service_project_link.project

    get_project.short_description = 'Project'
    get_project.admin_order_field = 'service_project_link__project__name'


class PublishableResourceAdmin(ResourceAdmin):
    list_display = ResourceAdmin.list_display + ('publishing_state',)


class VirtualMachineAdmin(ResourceAdmin):
    readonly_fields = ResourceAdmin.readonly_fields + ('image_name',)

    actions = ['detect_coordinates']

    def detect_coordinates(self, request, queryset):
        send_task('structure', 'detect_vm_coordinates_batch')([vm.to_string() for vm in queryset])

        tasks_scheduled = queryset.count()
        message = ungettext(
            'Coordinates detection has been scheduled for one virtual machine',
            'Coordinates detection has been scheduled for %(tasks_scheduled)d virtual machines',
            tasks_scheduled
        )
        message = message % {'tasks_scheduled': tasks_scheduled}

        self.message_user(request, message)

    detect_coordinates.short_description = "Detect coordinates of virtual machines"


admin.site.register(models.Customer, CustomerAdmin)
admin.site.register(models.Project, ProjectAdmin)
admin.site.register(models.ProjectGroup, ProjectGroupAdmin)
admin.site.register(models.ServiceSettings, ServiceSettingsAdmin)
