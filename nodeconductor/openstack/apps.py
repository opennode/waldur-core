from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.openstack import handlers
from nodeconductor.structure import SupportedServices


class OpenStackConfig(AppConfig):
    name = 'nodeconductor.openstack'
    verbose_name = "NodeConductor OpenStack"

    def ready(self):
        OpenStackService = self.get_model('OpenStackService')
        OpenStackServiceProjectLink = self.get_model('OpenStackServiceProjectLink')

        from nodeconductor.openstack.backend import OpenStackBackend
        SupportedServices.register_backend(OpenStackService, OpenStackBackend)

        signals.pre_save.connect(
            handlers.set_spl_default_availability_zone,
            sender=OpenStackServiceProjectLink,
            dispatch_uid='nodeconductor.openstack.handlers.set_spl_default_availability_zone',
        )
