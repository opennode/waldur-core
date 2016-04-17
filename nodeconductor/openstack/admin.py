from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse

from nodeconductor.core.admin import ExecutorAdminAction
from nodeconductor.structure import admin as structure_admin
from nodeconductor.openstack import executors
from nodeconductor.openstack.forms import BackupScheduleForm, InstanceForm
from nodeconductor.openstack.models import OpenStackService, OpenStackServiceProjectLink, Instance, \
                                           Backup, BackupSchedule, Tenant, Flavor


class ServiceProjectLinkAdmin(structure_admin.ServiceProjectLinkAdmin):
    list_display = structure_admin.ServiceProjectLinkAdmin.list_display + ('get_tenant',)
    readonly_fields = ('get_service_settings_username', 'get_service_settings_password', 'get_tenant') + \
        structure_admin.ServiceProjectLinkAdmin.readonly_fields

    def get_service_settings_username(self, obj):
        return obj.service.settings.username

    get_service_settings_username.short_description = 'Username'

    def get_service_settings_password(self, obj):
        return obj.service.settings.password

    get_service_settings_password.short_description = 'Password'

    def get_tenant(self, obj):
        tenant = obj.tenant
        if tenant is not None:
            url = reverse('admin:%s_%s_change' % (tenant._meta.app_label,  tenant._meta.model_name),  args=[tenant.id])
            return '<a href="%s">%s</a>' % (url, tenant.name)
        return

    get_tenant.short_description = 'Tenant'
    get_tenant.allow_tags = True


class BackupAdmin(admin.ModelAdmin):
    readonly_fields = ('created_at', 'kept_until')
    list_filter = ('uuid', 'state')
    list_display = ('uuid', 'instance', 'state')


class BackupScheduleAdmin(admin.ModelAdmin):
    form = BackupScheduleForm
    readonly_fields = ('next_trigger_at',)
    list_filter = ('is_active',)
    list_display = ('uuid', 'next_trigger_at', 'is_active', 'instance', 'timezone')


class InstanceAdmin(structure_admin.VirtualMachineAdmin):
    form = InstanceForm


class TenantAdmin(structure_admin.ResourceAdmin):

    actions = ('pull', 'detect_external_networks', 'allocate_floating_ip', 'pull_security_groups',
               'pull_floating_ips', 'pull_quotas')

    class OKTenantAction(ExecutorAdminAction):
        """ Execute action with tenant that is in state OK """

        def validate(self, tenant):
            if tenant.state != Tenant.States.OK:
                raise ValidationError('Tenant has to be in state OK to pull security groups.')

    class PullSecurityGroups(OKTenantAction):
        executor = executors.TenantPullSecurityGroupsExecutor
        short_description = 'Pull security groups'

    pull_security_groups = PullSecurityGroups()

    class AllocateFloatingIP(OKTenantAction):
        executor = executors.TenantAllocateFloatingIPExecutor
        short_description = 'Allocate floating IPs'

        def validate(self, tenant):
            super(TenantAdmin.AllocateFloatingIP, self).validate(tenant)
            if not tenant.exeternal_network_id:
                raise ValidationError('Tenant has to have external network to allocate floating IP.')

    allocate_floating_ip = AllocateFloatingIP()

    class DetectExternalNetwrorks(OKTenantAction):
        executor = executors.TenantDetectExternalNetworkExecutor
        short_description = 'Attempt to lookup and set external network id of the connected router'

    detect_external_networks = DetectExternalNetwrorks()

    class PullFloatingIPs(OKTenantAction):
        executor = executors.TenantPullFloatingIPsExecutor
        short_description = 'Pull floating IPs'

    pull_floating_ips = PullFloatingIPs()

    class PullQuotas(OKTenantAction):
        executor = executors.TenantPullQuotasExecutor
        short_description = 'Pull quotas'

    pull_quotas = PullQuotas()

    class Pull(ExecutorAdminAction):
        executor = executors.TenantPullExecutor
        short_description = 'Pull'

        def validate(self, tenant):
            if tenant.state not in (Tenant.States.OK, Tenant.States.ERRED):
                raise ValidationError('Tenant has to be OK or erred.')

    pull = Pull()


class FlavorAdmin(admin.ModelAdmin):
    list_filter = ('settings',)
    list_display = ('name', 'settings', 'cores', 'ram', 'disk')


admin.site.register(Instance, InstanceAdmin)
admin.site.register(Tenant, TenantAdmin)
admin.site.register(Flavor, FlavorAdmin)
admin.site.register(OpenStackService, structure_admin.ServiceAdmin)
admin.site.register(OpenStackServiceProjectLink, ServiceProjectLinkAdmin)
admin.site.register(Backup, BackupAdmin)
admin.site.register(BackupSchedule, BackupScheduleAdmin)
