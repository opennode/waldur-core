from django.apps import AppConfig

default_app_config = 'nodeconductor.structure.tests.TestConfig'


class TestConfig(AppConfig):
    name = 'nodeconductor.structure.tests'
    label = 'structure_tests'
    service_name = 'Test'

    def ready(self):
        from nodeconductor.structure import SupportedServices
        from .serializers import ServiceSerializer  # XXX: registry serializer

        TestService = self.get_model('TestService')
        TestInstance = self.get_model('TestInstance')

        SupportedServices._registry[self.service_name] = {
            'model_name': str(TestService._meta),
            'name': self.service_name,
            'resources': {
                str(TestInstance._meta): {'name': TestInstance.__class__.__name__},
            },
            'properties': {},
        }
