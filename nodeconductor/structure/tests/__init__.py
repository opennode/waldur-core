from django.apps import AppConfig

from nodeconductor.structure import SupportedServices, ServiceBackend


default_app_config = 'nodeconductor.structure.tests.TestConfig'


class TestBackend(ServiceBackend):
    def destroy(self, resource, force=False):
        pass


class TestConfig(AppConfig):
    name = 'nodeconductor.structure.tests'
    label = 'structure_tests'
    service_name = 'Test'

    def ready(self):
        SupportedServices.register_backend(TestBackend)
        SupportedServices.register_service(self.get_model('TestService'))
