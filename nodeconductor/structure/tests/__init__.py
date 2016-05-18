from django.apps import AppConfig

from nodeconductor.cost_tracking import CostTrackingRegister, CostTrackingBackend

default_app_config = 'nodeconductor.structure.tests.TestConfig'


class TestTrackingBackend(CostTrackingBackend):
    pass


class TestConfig(AppConfig):
    name = 'nodeconductor.structure.tests'
    label = 'structure_tests'
    service_name = 'Test'

    def ready(self):
        from nodeconductor.structure import SupportedServices, ServiceBackend
        from .serializers import ServiceSerializer  # XXX: registry serializer

        class TestBackend(ServiceBackend):
            def destroy(self, resource, force=False):
                pass

        SupportedServices.register_backend(TestBackend)
        CostTrackingRegister.register(self.label, TestTrackingBackend)
