from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.openstack import handlers
from nodeconductor.structure import SupportedServices


class OpenStackConfig(AppConfig):
    name = 'nodeconductor.openstack'
    verbose_name = "NodeConductor OpenStack"

    def ready(self):
        Service = self.get_model('Service')
        ServiceProjectLink = self.get_model('ServiceProjectLink')

        from nodeconductor.openstack.backend import OpenStackBackend
        SupportedServices.register_backend(Service, OpenStackBackend)

        signals.pre_save.connect(
            handlers.set_spl_default_availability_zone,
            sender=ServiceProjectLink,
            dispatch_uid='nodeconductor.openstack.handlers.set_spl_default_availability_zone',
        )
