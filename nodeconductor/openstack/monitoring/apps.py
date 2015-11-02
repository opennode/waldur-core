from django.apps import AppConfig

from nodeconductor.monitoring import MonitoringRegister


class OpenStackMonitoringConfig(AppConfig):
    name = 'nodeconductor.openstack.monitoring'
    verbose_name = "NodeConductor OpenStack monitoring"

    def ready(self):
        from nodeconductor.openstack import models as openstack_models

        MonitoringRegister.register_resource(openstack_models.Instance)
