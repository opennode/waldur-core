from django.apps import AppConfig

from nodeconductor.structure import SupportedServices


class OracleConfig(AppConfig):
    name = 'nodeconductor.oracle'
    verbose_name = "NodeConductor Oracle"

    def ready(self):
        OracleService = self.get_model('OracleService')

        from nodeconductor.oracle.backend import OracleBackend
        SupportedServices.register_backend(OracleService, OracleBackend)

        # XXX: I am not sure that this is right place for app registration in cost_tracking
        from nodeconductor.oracle.cost_tracking import register
        register()
