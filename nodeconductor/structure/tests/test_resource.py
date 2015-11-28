import factory

from rest_framework import test

from nodeconductor.iaas.models import OpenStackSettings
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.structure import SupportedServices
from nodeconductor.structure.models import CustomerRole
from nodeconductor.structure.tests import factories


class ResourceQuotasTest(test.APITransactionTestCase):

    def setUp(self):
        self.user = factories.UserFactory()
        self.customer = factories.CustomerFactory()
        self.customer.add_user(self.user, CustomerRole.OWNER)
        self.project = factories.ProjectFactory(customer=self.customer)

    def test_auto_quotas_update(self):
        for service_type, models in SupportedServices.get_service_models().items():
            settings = factories.ServiceSettingsFactory(customer=self.customer, type=service_type, shared=False)

            class ServiceFactory(factory.DjangoModelFactory):
                class Meta(object):
                    model = models['service']

            class ServiceProjectLinkFactory(factory.DjangoModelFactory):
                class Meta(object):
                    model = models['service_project_link']

            if service_type == SupportedServices.Types.IaaS:
                service = ServiceFactory(customer=self.customer, state=SynchronizationStates.IN_SYNC)
                OpenStackSettings.objects.get_or_create(
                    auth_url='http://example.com:5000/v2',
                    defaults={
                        'username': 'admin',
                        'password': 'password',
                        'tenant_name': 'admin',
                    })

            else:
                service = ServiceFactory(customer=self.customer, settings=settings)

            for resource_model in models['resources']:
                if not hasattr(resource_model, 'update_quota_usage'):
                    continue

                class ResourceFactory(factory.DjangoModelFactory):
                    class Meta(object):
                        model = resource_model

                data = {'cores': 4, 'ram': 1024, 'disk': 20480}

                service_project_link = ServiceProjectLinkFactory(service=service, project=self.project)
                resource = ResourceFactory(service_project_link=service_project_link, cores=data['cores'])

                self.assertEqual(service_project_link.quotas.get(name='instances').usage, 1)
                self.assertEqual(service_project_link.quotas.get(name='vcpu').usage, data['cores'])
                self.assertEqual(service_project_link.quotas.get(name='ram').usage, 0)
                self.assertEqual(service_project_link.quotas.get(name='storage').usage, 0)

                resource.ram = data['ram']
                resource.disk = data['disk']
                resource.save()

                self.assertEqual(service_project_link.quotas.get(name='ram').usage, data['ram'])
                self.assertEqual(service_project_link.quotas.get(name='storage').usage, data['disk'])

                resource.delete()
                self.assertEqual(service_project_link.quotas.get(name='instances').usage, 0)
                self.assertEqual(service_project_link.quotas.get(name='vcpu').usage, 0)
                self.assertEqual(service_project_link.quotas.get(name='ram').usage, 0)
                self.assertEqual(service_project_link.quotas.get(name='storage').usage, 0)
