from django import forms
from django.contrib import admin, messages
from django.utils.translation import ungettext, gettext
from django.utils.translation import ugettext_lazy as _

from nodeconductor.core.models import SynchronizationStates
from nodeconductor.core.tasks import send_task
from nodeconductor.monitoring.zabbix.errors import ZabbixError
from nodeconductor.iaas import models
from nodeconductor.iaas import tasks
from nodeconductor.quotas.admin import QuotaInline
from nodeconductor.structure.admin import ProtectedModelMixin


# Inspired by Django Snippet https://djangosnippets.org/snippets/2629/
class ReadonlyInlineMixin(object):
    can_delete = False
    extra = 0

    def has_add_permission(self, request):
        return False


class FlavorInline(admin.TabularInline):
    model = models.Flavor
    extra = 1


# noinspection PyMethodMayBeStatic
class CloudAdmin(admin.ModelAdmin):
    inlines = (
        FlavorInline,
    )
    list_display = ('name', 'customer', 'state')
    ordering = ('name', 'customer')

    actions = ['sync_services']

    def sync_services(self, request, queryset):
        queryset = queryset.filter(state=SynchronizationStates.IN_SYNC)
        service_uuids = list(queryset.values_list('uuid', flat=True))
        tasks_scheduled = queryset.count()

        tasks.sync_services.delay(service_uuids)

        message = ungettext(
            'One cloud account scheduled for update',
            '%(tasks_scheduled)d cloud accounts scheduled for update',
            tasks_scheduled
        )
        message = message % {
            'tasks_scheduled': tasks_scheduled,
        }

        self.message_user(request, message)

    sync_services.short_description = "Update selected cloud accounts from backend"


# noinspection PyMethodMayBeStatic
class CloudProjectMembershipAdmin(admin.ModelAdmin):
    readonly_fields = ('cloud', 'project')
    list_display = ('get_cloud_name', 'get_customer_name', 'get_project_name', 'state', 'tenant_id')
    ordering = ('cloud__customer__name', 'project__name', 'cloud__name')
    list_display_links = ('get_cloud_name',)
    search_fields = ('cloud__customer__name', 'project__name', 'cloud__name')
    inlines = [QuotaInline]

    actions = ['pull_cloud_memberships', 'recover_erred_cloud_memberships',
               'detect_external_networks', 'allocate_floating_ip']

    def get_queryset(self, request):
        queryset = super(CloudProjectMembershipAdmin, self).get_queryset(request)
        return queryset.select_related('cloud', 'project', 'project__customer')

    def pull_cloud_memberships(self, request, queryset):
        # TODO: Extract to a service

        queryset = queryset.filter(state=SynchronizationStates.IN_SYNC)

        tasks_scheduled = 0

        for membership in queryset.iterator():
            membership.schedule_syncing()
            membership.save()

            tasks.pull_cloud_membership.delay(membership.pk)
            tasks_scheduled += 1

        message = ungettext(
            'One cloud project membership scheduled for update',
            '%(tasks_scheduled)d cloud project memberships scheduled for update',
            tasks_scheduled
        )
        message = message % {
            'tasks_scheduled': tasks_scheduled,
        }

        self.message_user(request, message)

    pull_cloud_memberships.short_description = "Update selected cloud project memberships from backend"

    def recover_erred_cloud_memberships(self, request, queryset):
        queryset = queryset.filter(state=SynchronizationStates.ERRED)
        tasks_scheduled = queryset.count()
        if tasks_scheduled:
            send_task('structure', 'recover_erred_services')([spl.to_string() for spl in queryset])

        message = ungettext(
            'One cloud project membership scheduled for recovery',
            '%(tasks_scheduled)d cloud project memberships scheduled for recovery',
            tasks_scheduled
        )
        message = message % {
            'tasks_scheduled': tasks_scheduled,
        }

        self.message_user(request, message)

    recover_erred_cloud_memberships.short_description = "Recover selected cloud project memberships"

    def detect_external_networks(self, request, queryset):
        queryset = queryset.exclude(state=SynchronizationStates.ERRED)

        tasks_scheduled = 0

        for membership in queryset.iterator():
            tasks.detect_external_network.delay(membership.pk)
            tasks_scheduled += 1

        message = ungettext(
            'One cloud project membership scheduled for detection',
            '%(tasks_scheduled)d cloud project memberships scheduled for detection',
            tasks_scheduled
        )
        message = message % {
            'tasks_scheduled': tasks_scheduled,
        }

        self.message_user(request, message)

    detect_external_networks.short_description = "Attempt to lookup and set external network id of the connected router"

    def allocate_floating_ip(self, request, queryset):
        queryset = queryset.exclude(state=SynchronizationStates.ERRED).exclude(external_network_id='')

        tasks_scheduled = 0

        for membership in queryset.iterator():
            tasks.allocate_floating_ip.delay(membership.pk)
            tasks_scheduled += 1

        message = ungettext(
            'One cloud project membership scheduled for floating IP allocation',
            '%(tasks_scheduled)d cloud project memberships scheduled for floating IP allocation',
            tasks_scheduled
        )
        message = message % {
            'tasks_scheduled': tasks_scheduled,
        }

        self.message_user(request, message)

    allocate_floating_ip.short_description = "Allocate floating IPs for selected cloud project memberships"

    def get_cloud_name(self, obj):
        return obj.cloud.name

    get_cloud_name.short_description = 'Cloud'

    def get_project_name(self, obj):
        return obj.project.name

    get_project_name.short_description = 'Project'

    def get_customer_name(self, obj):
        return obj.cloud.customer.name

    get_customer_name.short_description = 'Customer'


class InstanceLicenseInline(admin.TabularInline):
    model = models.InstanceLicense
    extra = 1


class InstanceAdmin(ProtectedModelMixin, admin.ModelAdmin):
    inlines = (
        InstanceLicenseInline,
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['template']
        return []
    ordering = ('name',)
    list_display = ['name', 'uuid', 'backend_id', 'state', 'installation_state', 'get_project_name', 'template']
    search_fields = ['name', 'uuid']
    list_filter = ['state', 'cloud_project_membership__project', 'template']

    actions = ['pull_installation_state', 'subscribe']

    fieldsets = (
        (_('General'), {'fields': ('name', 'description', 'cloud_project_membership')}),
        (_('State'), {'fields': ('state', 'installation_state', 'start_time')}),
        (_('Flavor configuration'), {'fields': ('flavor_name', 'cores', 'ram',)}),
        (_('Storage configuration'), {'fields': ('system_volume_id', 'system_volume_size', 'data_volume_id', 'data_volume_size',)}),
        (_('Access configuration'), {'fields': ('key_name', 'key_fingerprint')}),
        (_('Network configuration'), {'fields': ('internal_ips', 'external_ips')}),
        (_('Deployment settings'), {'fields': ('template', 'type', 'agreed_sla', 'user_data')}),
        (_('Billing'), {'fields': ('billing_backend_id',)}),
    )

    def get_project_name(self, obj):
        return obj.cloud_project_membership.project.name

    get_project_name.short_description = 'Project'

    def pull_installation_state(self, request, queryset):
        erred_instances = []
        for instance in queryset:
            try:
                # This code has to be refactored in NC-580 because it is not DRY (duplications in tasks)
                installation_state = tasks.zabbix._get_installation_state(instance)
                if installation_state in ['NO DATA', 'NOT OK'] and instance.installation_state in ['FAIL', 'OK']:
                    installation_state = 'FAIL'
                if instance.installation_state != installation_state:
                    instance.installation_state = installation_state
                    instance.save()
            except ZabbixError:
                erred_instances.append(instance)

        if not erred_instances:
            message = gettext('Installation state of selected instances was pulled successfully')
        else:
            message = gettext('Pulling failed for instances: %(erred_instances)s')
        message = message % {'erred_instances': ', '.join([i.name for i in erred_instances])}

        self.message_user(request, message)

    pull_installation_state.short_description = "Pull Installation state"

    def subscribe(self, request, queryset):
        erred_instances = []
        subscribed_instances = []
        for instance in queryset:
            is_subscribed, _ = instance.order.subscribe()
            if is_subscribed:
                subscribed_instances.append(instance)
            else:
                erred_instances.append(instance)

        if subscribed_instances:
            subscribed_instances_count = len(subscribed_instances)
            message = ungettext(
                'One instance subscribed',
                '%(subscribed_instances_count)d instances subscribed',
                subscribed_instances_count
            )
            message = message % {'subscribed_instances_count': subscribed_instances_count}
            self.message_user(request, message)

        if erred_instances:
            message = gettext('Failed to subscribe instances: %(erred_instances)s')
            message = message % {'erred_instances': ', '.join([i.name for i in erred_instances])}
            self.message_user(request, message, level=messages.ERROR)

    subscribe.short_description = "Subscribe to billing backend"


class ImageInline(ReadonlyInlineMixin, admin.TabularInline):
    model = models.Image
    fields = ('get_cloud_name', 'get_customer_name', 'backend_id')
    readonly_fields = ('get_cloud_name', 'get_customer_name', 'backend_id')
    ordering = ('cloud__name', 'cloud__customer__name')
    verbose_name_plural = 'Connected cloud images'

    def get_cloud_name(self, obj):
        return obj.cloud.name
    get_cloud_name.short_description = 'Cloud'

    def get_customer_name(self, obj):
        return obj.cloud.customer.name
    get_customer_name.short_description = 'Customer'


class TemplateMappingInline(admin.TabularInline):
    model = models.TemplateMapping
    fields = ('description', 'backend_image_id')
    ordering = ('description', )
    extra = 3


class LicenseInlineFormSet(forms.models.BaseInlineFormSet):
    def clean(self):
        licenses = {}
        for form in self.forms:
            license = form.cleaned_data.get('templatelicense')
            del_key = form.add_prefix('DELETE')
            if license and del_key not in form.data:
                licenses.setdefault(license.service_type, [])
                licenses[license.service_type].append(license)

        for service_type, data in licenses.items():
            if len(data) > 1:
                raise forms.ValidationError(
                    "Only one license of service type %s is allowed" % service_type)


class LicenseInline(admin.TabularInline):
    model = models.TemplateLicense.templates.through
    formset = LicenseInlineFormSet
    verbose_name_plural = 'Connected licenses'
    extra = 1


class TemplateAdmin(admin.ModelAdmin):
    inlines = (
        TemplateMappingInline,
        ImageInline,
        LicenseInline,
    )
    ordering = ('name', )
    list_display = ['name', 'uuid', 'os_type', 'application_type', 'type', 'sla_level']

    fieldsets = (
        (_('General'), {'fields': ('name', 'description', 'icon_name', 'is_active',)}),
        (_('Type'), {'fields': ('os', 'os_type', 'application_type', 'type',)}),
        (_('Deployment settings'), {'fields': ('sla_level',)}),
    )


class FlavorInline(admin.TabularInline):
    model = models.Flavor
    extra = 1


class SecurityGroupRuleInline(admin.TabularInline):
    model = models.SecurityGroupRule
    extra = 1


class SecurityGroupAdmin(admin.ModelAdmin):
    inlines = (
        SecurityGroupRuleInline,
    )
    list_display = ('cloud_project_membership', 'name')
    ordering = ('cloud_project_membership', 'name')


class InstanceSlaHistoryEventsInline(admin.TabularInline):
    model = models.InstanceSlaHistoryEvents
    fields = ('timestamp', 'state')
    ordering = ('timestamp', )
    extra = 1


class InstanceSlaHistoryAdmin(admin.ModelAdmin):
    inlines = (
        InstanceSlaHistoryEventsInline,
    )
    list_display = ('instance', 'period',  'value')
    list_filter = ('instance', 'period')


class FloatingIPAdmin(admin.ModelAdmin):
    list_display = ('cloud_project_membership', 'address', 'status')
    readonly_fields = ('backend_network_id',)


admin.site.register(models.Cloud, CloudAdmin)
admin.site.register(models.CloudProjectMembership, CloudProjectMembershipAdmin)
admin.site.register(models.Instance, InstanceAdmin)
admin.site.register(models.SecurityGroup, SecurityGroupAdmin)
admin.site.register(models.Template, TemplateAdmin)
admin.site.register(models.TemplateLicense)
admin.site.register(models.InstanceSlaHistory, InstanceSlaHistoryAdmin)
admin.site.register(models.FloatingIP, FloatingIPAdmin)
admin.site.register(models.IpMapping)
admin.site.register(models.OpenStackSettings)
