import json

from django.conf import settings
from django.conf.urls import url
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import ValidationError
from django.db import models as django_models
from django.forms import ModelMultipleChoiceField, ModelForm, TypedChoiceField, RadioSelect, ChoiceField
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils import six
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ungettext
from jsoneditor.forms import JSONEditor

from nodeconductor.core import utils as core_utils
from nodeconductor.core.admin import get_admin_url, ExecutorAdminAction
from nodeconductor.core.models import User
from nodeconductor.core.tasks import send_task
from nodeconductor.quotas.admin import QuotaInline
from nodeconductor.structure import models, SupportedServices, executors, utils, managers


class BackendModelAdmin(admin.ModelAdmin):

    def has_add_permission(self, request):
        return False

    def get_readonly_fields(self, request, obj=None):
        fields = super(BackendModelAdmin, self).get_readonly_fields(request, obj)

        if not obj:
            return fields

        if not settings.NODECONDUCTOR['BACKEND_FIELDS_EDITABLE']:
            instance_class = type(obj)
            fields = fields + instance_class.get_backend_fields()

        return fields


class FormRequestAdminMixin(object):
    """
    This mixin allows you to get current request user in the model admin form,
    which then passed to add_user method, so that user which granted role,
    is stored in the permission model.
    """
    def get_form(self, request, obj=None, **kwargs):
        form = super(FormRequestAdminMixin, self).get_form(request, obj=obj, **kwargs)
        form.request = request
        return form


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

    get_vm_count.short_description = _('VM count')

    def get_app_count(self, obj):
        return obj.quotas.get(name=obj.Quotas.nc_app_count).usage

    get_app_count.short_description = _('Application count')

    def get_private_cloud_count(self, obj):
        return obj.quotas.get(name=obj.Quotas.nc_private_cloud_count).usage

    get_private_cloud_count.short_description = _('Private cloud count')


class CustomerAdminForm(ModelForm):
    owners = ModelMultipleChoiceField(User.objects.all().order_by('full_name'), required=False,
                                      widget=FilteredSelectMultiple(verbose_name=_('Owners'), is_stacked=False))
    support_users = ModelMultipleChoiceField(User.objects.all().order_by('full_name'), required=False,
                                             widget=FilteredSelectMultiple(verbose_name=_('Support users'),
                                                                           is_stacked=False))

    def __init__(self, *args, **kwargs):
        super(CustomerAdminForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.owners = self.instance.get_owners()
            self.support_users = self.instance.get_support_users()
            self.fields['owners'].initial = self.owners
            self.fields['support_users'].initial = self.support_users
        else:
            self.owners = User.objects.none()
            self.support_users = User.objects.none()

    def save(self, commit=True):
        customer = super(CustomerAdminForm, self).save(commit=False)

        if not customer.pk:
            customer.save()

        self.populate_users('owners', customer, models.CustomerRole.OWNER)
        self.populate_users('support_users', customer, models.CustomerRole.SUPPORT)

        return customer

    def populate_users(self, field_name, customer, role):
        field = getattr(self, field_name)
        new_users = self.cleaned_data[field_name]

        removed_users = field.exclude(pk__in=new_users)
        for user in removed_users:
            customer.remove_user(user, role)

        added_users = new_users.exclude(pk__in=field)
        for user in added_users:
            # User role within customer must be unique.
            if not customer.has_user(user):
                customer.add_user(user, role, self.request.user)

        self.save_m2m()


class CustomerAdmin(FormRequestAdminMixin,
                    ResourceCounterFormMixin,
                    ProtectedModelMixin,
                    admin.ModelAdmin):
    form = CustomerAdminForm
    fields = ('name', 'image', 'native_name', 'abbreviation', 'contact_details', 'registration_code',
              'country', 'vat_code', 'is_company', 'balance', 'owners', 'support_users')
    readonly_fields = ['balance']
    list_display = ['name', 'uuid', 'abbreviation', 'created', 'get_vm_count', 'get_app_count',
                    'get_private_cloud_count']
    inlines = [QuotaInline]


class ProjectAdminForm(ModelForm):
    admins = ModelMultipleChoiceField(User.objects.all().order_by('full_name'), required=False,
                                      widget=FilteredSelectMultiple(verbose_name=_('Admins'), is_stacked=False))
    managers = ModelMultipleChoiceField(User.objects.all().order_by('full_name'), required=False,
                                        widget=FilteredSelectMultiple(verbose_name=_('Managers'), is_stacked=False))
    support_users = ModelMultipleChoiceField(User.objects.all().order_by('full_name'), required=False,
                                             widget=FilteredSelectMultiple(verbose_name=_('Support users'),
                                                                           is_stacked=False))

    def __init__(self, *args, **kwargs):
        super(ProjectAdminForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.admins = self.instance.get_users(models.ProjectRole.ADMINISTRATOR)
            self.managers = self.instance.get_users(models.ProjectRole.MANAGER)
            self.support_users = self.instance.get_users(models.ProjectRole.SUPPORT)
            self.fields['admins'].initial = self.admins
            self.fields['managers'].initial = self.managers
            self.fields['support_users'].initial = self.support_users
        else:
            for field_name in ('admins', 'managers', 'support_users'):
                setattr(self, field_name, User.objects.none())

    def save(self, commit=True):
        project = super(ProjectAdminForm, self).save(commit=False)

        if not project.pk:
            project.save()

        self.populate_users('admins', project, models.ProjectRole.ADMINISTRATOR)
        self.populate_users('managers', project, models.ProjectRole.MANAGER)
        self.populate_users('support_users', project, models.ProjectRole.SUPPORT)

        return project

    def populate_users(self, field_name, project, role):
        field = getattr(self, field_name)
        new_users = self.cleaned_data[field_name]

        removed_users = field.exclude(pk__in=new_users)
        for user in removed_users:
            project.remove_user(user, role)

        added_users = new_users.exclude(pk__in=field)
        for user in added_users:
            # User role within project must be unique.
            if not project.has_user(user):
                project.add_user(user, role, self.request.user)
        self.save_m2m()


class ProjectAdmin(FormRequestAdminMixin,
                   ResourceCounterFormMixin,
                   ProtectedModelMixin,
                   ChangeReadonlyMixin,
                   admin.ModelAdmin):
    form = ProjectAdminForm

    fields = ('name', 'description', 'customer', 'admins', 'managers', 'support_users', 'certifications')

    list_display = ['name', 'uuid', 'customer', 'created', 'get_vm_count', 'get_app_count', 'get_private_cloud_count']
    search_fields = ['name', 'uuid']
    change_readonly_fields = ['customer']
    inlines = [QuotaInline]
    filter_horizontal = ('certifications',)


class ServiceCertificationAdmin(admin.ModelAdmin):
    list_display = ('name', 'link')
    search_fields = ['name', 'link']
    list_filter = ('service_settings',)


class ServiceSettingsAdminForm(ModelForm):
    shared = TypedChoiceField(
        coerce=lambda x: x == 'True',
        choices=((True, _('Yes (Anybody can use it)')), (False, _('No (Only available to me)'))),
        widget=RadioSelect,
    )

    class Meta:
        widgets = {
            'options': JSONEditor(),
            'geolocations': JSONEditor(),
        }

    def __init__(self, *args, **kwargs):
        super(ServiceSettingsAdminForm, self).__init__(*args, **kwargs)
        self.fields['type'] = ChoiceField(choices=SupportedServices.get_choices(),
                                          widget=RadioSelect)

    def clean(self):
        shared = self.cleaned_data.get('shared', False)
        if shared and self.cleaned_data.get('customer') is not None:
            raise ValidationError(_('Shared service settings should not be connected to any customer.'))

        return super(ServiceSettingsAdminForm, self).clean()


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
    list_display = ('name', 'customer', 'get_type_display', 'state', 'error_message')
    list_filter = (ServiceTypeFilter, 'state')
    change_readonly_fields = ('shared', 'customer')
    actions = ['pull', 'connect_shared']
    form = ServiceSettingsAdminForm
    fields = ('type', 'name', 'shared', 'backend_url', 'username', 'password',
              'token', 'domain', 'certificate', 'options', 'customer',
              'state', 'error_message', 'tags', 'homepage', 'terms_of_services',
              'certifications', 'geolocations')
    inlines = [QuotaInline]
    filter_horizontal = ('certifications',)
    common_fields = ('type', 'name', 'shared', 'state', 'options', 'geolocations', 'certifications')

    # must be specified explicitly not to be constructed from model name by default.
    change_form_template = 'admin/structure/servicesettings/change_form.html'

    def get_type_display(self, obj):
        return obj.get_type_display()
    get_type_display.short_description = 'Type'

    def add_view(self, *args, **kwargs):
        self.exclude = getattr(self, 'add_exclude', ())
        return super(ServiceSettingsAdmin, self).add_view(*args, **kwargs)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        service_field_names = utils.get_all_services_field_names()
        for service_name in service_field_names:
            service_field_names[service_name].extend(self.common_fields)
        extra_context['service_fields'] = json.dumps(service_field_names)
        return super(ServiceSettingsAdmin, self).changeform_view(request, object_id, form_url, extra_context)

    def get_readonly_fields(self, request, obj=None):
        fields = super(ServiceSettingsAdmin, self).get_readonly_fields(request, obj)
        if not obj:
            return fields + ('state',)
        return fields

    def get_form(self, request, obj=None, **kwargs):
        # filter out certain fields from the creation form
        form = super(ServiceSettingsAdmin, self).get_form(request, obj, **kwargs)
        if 'shared' in form.base_fields:
            form.base_fields['shared'].initial = True if self.model is models.SharedServiceSettings else False
            form.base_fields['shared'].widget.attrs['disabled'] = True

        return form

    def get_urls(self):
        my_urls = [
            url(r'^(.+)/change/services/$', self.admin_site.admin_view(self.services)),
        ]
        return my_urls + super(ServiceSettingsAdmin, self).get_urls()

    def services(self, request, pk=None):
        settings = models.ServiceSettings.objects.get(id=pk)
        projects = {}

        spl_model = SupportedServices.get_related_models(settings)['service_project_link']
        for spl in spl_model.objects.filter(service__settings=settings):
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
        short_description = _('Pull')

        def validate(self, service_settings):
            States = models.ServiceSettings.States
            if service_settings.state not in (States.OK, States.ERRED):
                raise ValidationError(_('Service settings has to be OK or erred.'))

    pull = Pull()

    class ConnectShared(ExecutorAdminAction):
        executor = executors.ServiceSettingsConnectSharedExecutor
        short_description = _('Create SPLs and services for shared service settings')

        def validate(self, service_settings):
            if not service_settings.shared:
                raise ValidationError(_('It is impossible to connect not shared settings.'))

    connect_shared = ConnectShared()

    def save_model(self, request, obj, form, change):
        obj.save()
        if not change:
            executors.ServiceSettingsCreateExecutor.execute(obj)


class ServiceAdmin(admin.ModelAdmin):
    list_display = ('settings', 'customer')
    ordering = ('customer',)


class ServiceProjectLinkAdmin(admin.ModelAdmin):
    readonly_fields = ('service', 'project')
    list_display = ('get_service_name', 'get_customer_name', 'get_project_name')
    list_filter = ('service__settings', 'project__name', 'service__settings__name')
    ordering = ('service__customer__name', 'project__name')
    list_display_links = ('get_service_name',)
    search_fields = ('service__customer__name', 'project__name', 'service__settings__name')
    inlines = [QuotaInline]

    def get_queryset(self, request):
        queryset = super(ServiceProjectLinkAdmin, self).get_queryset(request)
        return queryset.select_related('service', 'project', 'project__customer')

    def get_service_name(self, obj):
        return obj.service.settings.name

    get_service_name.short_description = _('Service')

    def get_project_name(self, obj):
        return obj.project.name

    get_project_name.short_description = _('Project')

    def get_customer_name(self, obj):
        return obj.service.customer.name

    get_customer_name.short_description = _('Customer')


class DerivedFromSharedSettingsResourceFilter(SimpleListFilter):
    title = _('service settings')
    parameter_name = 'shared__exact'

    def lookups(self, request, model_admin):
        return ((1, _('Shared')), (0, _('Private')))

    def queryset(self, request, queryset):
        if self.value() is not None:
            return queryset.filter(service_project_link__service__settings__shared=self.value())
        else:
            return queryset


class ResourceAdmin(BackendModelAdmin):
    readonly_fields = ('error_message',)
    list_display = ('uuid', 'name', 'backend_id', 'state', 'created',
                    'get_service', 'get_project', 'error_message', 'get_settings_shared')
    list_filter = ('state', DerivedFromSharedSettingsResourceFilter)

    def get_settings_shared(self, obj):
        return obj.service_project_link.service.settings.shared

    get_settings_shared.short_description = _('Are service settings shared')

    def get_service(self, obj):
        return obj.service_project_link.service

    get_service.short_description = _('Service')
    get_service.admin_order_field = 'service_project_link__service__settings__name'

    def get_project(self, obj):
        return obj.service_project_link.project

    get_project.short_description = _('Project')
    get_project.admin_order_field = 'service_project_link__project__name'


class PublishableResourceAdmin(ResourceAdmin):
    list_display = ResourceAdmin.list_display + ('publishing_state',)


class VirtualMachineAdmin(ResourceAdmin):
    readonly_fields = ResourceAdmin.readonly_fields + ('image_name',)

    actions = ['detect_coordinates']

    def detect_coordinates(self, request, queryset):
        send_task('structure', 'detect_vm_coordinates_batch')([core_utils.serialize_instance(vm) for vm in queryset])

        tasks_scheduled = queryset.count()
        message = ungettext(
            'Coordinates detection has been scheduled for one virtual machine.',
            'Coordinates detection has been scheduled for %(tasks_scheduled)d virtual machines.',
            tasks_scheduled
        )
        message = message % {'tasks_scheduled': tasks_scheduled}

        self.message_user(request, message)

    detect_coordinates.short_description = _('Detect coordinates of virtual machines')


class SharedServiceSettings(models.ServiceSettings):
    """Required for a clear separation of shared/unshared service settings on admin."""

    objects = managers.SharedServiceSettingsManager()

    class Meta(object):
        proxy = True
        verbose_name_plural = 'Shared service settings'


class PrivateServiceSettings(models.ServiceSettings):
    """Required for a clear separation of shared/unshared service settings on admin."""

    objects = managers.PrivateServiceSettingsManager()

    class Meta(object):
        proxy = True
        verbose_name_plural = 'Private service settings'


admin.site.register(models.ServiceCertification, ServiceCertificationAdmin)
admin.site.register(models.Customer, CustomerAdmin)
admin.site.register(models.Project, ProjectAdmin)
admin.site.register(PrivateServiceSettings, ServiceSettingsAdmin)
admin.site.register(SharedServiceSettings, ServiceSettingsAdmin)
