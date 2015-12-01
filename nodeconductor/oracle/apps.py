from django.apps import AppConfig

from nodeconductor.structure import SupportedServices


class OracleConfig(AppConfig):
    name = 'nodeconductor.oracle'
    verbose_name = "NodeConductor Oracle"
    service_name = 'Oracle'

    def ready(self):
        OracleService = self.get_model('OracleService')

        from nodeconductor.oracle.backend import OracleBackend
        SupportedServices.register_backend(OracleBackend)
