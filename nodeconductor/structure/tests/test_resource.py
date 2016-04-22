import factory

from rest_framework import test, status

from nodeconductor.openstack.tests.factories import InstanceFactory
from nodeconductor.structure import SupportedServices
from nodeconductor.structure.models import CustomerRole, Resource
from nodeconductor.structure.tests import factories


class ResourceQuotasTest(test.APITransactionTestCase):

    def setUp(self):
        self.user = factories.UserFactory()
        self.customer = factories.CustomerFactory()
        self.customer.add_user(self.user, CustomerRole.OWNER)
        self.project = factories.ProjectFactory(customer=self.customer)

    def test_auto_quotas_update(self):
        service_type = 'OpenStack'
        models = SupportedServices.get_service_models()[service_type]
        settings = factories.ServiceSettingsFactory(customer=self.customer, type=service_type, shared=False)

        class ServiceFactory(factory.DjangoModelFactory):
            class Meta(object):
                model = models['service']

        class ServiceProjectLinkFactory(factory.DjangoModelFactory):
            class Meta(object):
                model = models['service_project_link']

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


class ResourceRemovalTest(test.APITransactionTestCase):
    def setUp(self):
        self.user = factories.UserFactory(is_staff=True)
        self.client.force_authenticate(user=self.user)

    def test_vm_unlinked_immediately_anyway(self):
        vm = InstanceFactory(state=Resource.States.PROVISIONING_SCHEDULED)
        url = InstanceFactory.get_url(vm, 'unlink')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)

    def test_vm_without_backend_id_removed_immediately(self):
        vm = InstanceFactory(state=Resource.States.OFFLINE)
        url = InstanceFactory.get_url(vm)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)

    def test_vm_with_backend_id_scheduled_to_deletion(self):
        vm = InstanceFactory(state=Resource.States.OFFLINE, backend_id=123)
        url = InstanceFactory.get_url(vm)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
