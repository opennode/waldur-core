from django.apps import AppConfig

from nodeconductor.structure import SupportedServices


class OracleConfig(AppConfig):
    name = 'nodeconductor.oracle'
    verbose_name = "NodeConductor Oracle"

    def ready(self):
        Service = self.get_model('Service')

        from nodeconductor.oracle.backend import OracleBackend
        SupportedServices.register_backend(Service, OracleBackend)
