from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.cost_tracking import CostTrackingRegister
from nodeconductor.quotas import handlers as quotas_handlers
from nodeconductor.openstack import handlers
from nodeconductor.structure import SupportedServices
from nodeconductor.structure.models import Project


class OpenStackConfig(AppConfig):
    """ OpenStack is a toolkit for building private and public clouds.
        This application adds support for managing OpenStack deployments -
        tenants, instances, security groups and networks.
    """
    name = 'nodeconductor.openstack'
    verbose_name = 'NodeConductor OpenStack'
    service_name = 'OpenStack'

    def ready(self):
        OpenStackServiceProjectLink = self.get_model('OpenStackServiceProjectLink')
        Instance = self.get_model('Instance')
        FloatingIP = self.get_model('FloatingIP')
        BackupSchedule = self.get_model('BackupSchedule')

        # structure
        from nodeconductor.openstack.backend import OpenStackBackend
        SupportedServices.register_backend(OpenStackBackend)

        # cost tracking
        from nodeconductor.openstack.cost_tracking import OpenStackCostTrackingBackend
        CostTrackingRegister.register(self.label, OpenStackCostTrackingBackend)

        # template
        from nodeconductor.template import TemplateRegistry
        from nodeconductor.openstack.template import InstanceProvisionTemplateForm
        TemplateRegistry.register(InstanceProvisionTemplateForm)

        signals.post_save.connect(
            handlers.create_initial_security_groups,
            sender=OpenStackServiceProjectLink,
            dispatch_uid='nodeconductor.openstack.handlers.create_initial_security_groups',
        )

        signals.post_save.connect(
            quotas_handlers.add_quotas_to_scope,
            sender=OpenStackServiceProjectLink,
            dispatch_uid='nodeconductor.openstack.handlers.add_quotas_to_service_project_link',
        )

        signals.pre_save.connect(
            handlers.set_spl_default_availability_zone,
            sender=OpenStackServiceProjectLink,
            dispatch_uid='nodeconductor.openstack.handlers.set_spl_default_availability_zone',
        )

        signals.post_save.connect(
            handlers.increase_quotas_usage_on_instance_creation,
            sender=Instance,
            dispatch_uid='nodeconductor.openstack.handlers.increase_quotas_usage_on_instance_creation',
        )

        signals.post_delete.connect(
            handlers.decrease_quotas_usage_on_instances_deletion,
            sender=Instance,
            dispatch_uid='nodeconductor.openstack.handlers.decrease_quotas_usage_on_instances_deletion',
        )

        signals.post_save.connect(
            handlers.change_floating_ip_quota_on_status_change,
            sender=FloatingIP,
            dispatch_uid='nodeconductor.openstack.handlers.change_floating_ip_quota_on_status_change',
        )
        signals.post_save.connect(
            handlers.check_project_name_update,
            sender=Project,
            dispatch_uid='nodeconductor.openstack.handlers.check_project_name_update',
        )

        signals.post_save.connect(
            handlers.log_backup_schedule_save,
            sender=BackupSchedule,
            dispatch_uid='nodeconductor.openstack.handlers.log_backup_schedule_save',
        )

        signals.post_delete.connect(
            handlers.log_backup_schedule_delete,
            sender=BackupSchedule,
            dispatch_uid='nodeconductor.openstack.handlers.log_backup_schedule_delete',
        )
