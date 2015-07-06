from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.openstack import handlers


class IaasConfig(AppConfig):
    name = 'nodeconductor.openstack'
    verbose_name = "NodeConductor OpenStack"

    def ready(self):
        OpenStackServiceProjectLink = self.get_model('OpenStackServiceProjectLink')

        signals.pre_save.connect(
            handlers.set_spl_default_availability_zone,
            sender=OpenStackServiceProjectLink,
            dispatch_uid='nodeconductor.openstack.handlers.set_spl_default_availability_zone',
        )
