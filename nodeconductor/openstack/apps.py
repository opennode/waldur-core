from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.quotas import handlers as quotas_handlers
from nodeconductor.openstack import handlers
from nodeconductor.structure import SupportedServices


class OpenStackConfig(AppConfig):
    name = 'nodeconductor.openstack'
    verbose_name = "NodeConductor OpenStack"

    def ready(self):
        OpenStackService = self.get_model('OpenStackService')
        OpenStackServiceProjectLink = self.get_model('OpenStackServiceProjectLink')
        Instance = self.get_model('Instance')

        from nodeconductor.openstack.backend import OpenStackBackend
        SupportedServices.register_backend(OpenStackService, OpenStackBackend)

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
            dispatch_uid='nodeconductor.iaas.handlers.increase_quotas_usage_on_instance_creation',
        )

        signals.post_delete.connect(
            handlers.decrease_quotas_usage_on_instances_deletion,
            sender=Instance,
            dispatch_uid='nodeconductor.iaas.handlers.decrease_quotas_usage_on_instances_deletion',
        )
