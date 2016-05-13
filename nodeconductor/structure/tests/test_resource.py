import unittest

from rest_framework import test, status

from nodeconductor.structure.models import CustomerRole, Resource
from nodeconductor.structure.tests import factories


class ResourceQuotasTest(test.APITransactionTestCase):

    def setUp(self):
        self.user = factories.UserFactory()
        self.customer = factories.CustomerFactory()
        self.customer.add_user(self.user, CustomerRole.OWNER)
        self.project = factories.ProjectFactory(customer=self.customer)

    def test_auto_quotas_update(self):
        settings = factories.ServiceSettingsFactory(customer=self.customer, shared=False)
        service = factories.TestServiceFactory(customer=self.customer, settings=settings)

        data = {'cores': 4, 'ram': 1024, 'disk': 20480}

        service_project_link = factories.TestServiceProjectLinkFactory(service=service, project=self.project)
        resource = factories.TestInstanceFactory(service_project_link=service_project_link, cores=data['cores'])

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


@unittest.skip("NC-1392: Test resource's view should be available")
class ResourceRemovalTest(test.APITransactionTestCase):
    def setUp(self):
        self.user = factories.UserFactory(is_staff=True)
        self.client.force_authenticate(user=self.user)

    def test_vm_unlinked_immediately_anyway(self):
        vm = factories.TestInstanceFactory(state=Resource.States.PROVISIONING_SCHEDULED)
        url = factories.TestInstanceFactory.get_url(vm, 'unlink')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)

    def test_vm_without_backend_id_removed_immediately(self):
        vm = factories.TestInstanceFactory(state=Resource.States.OFFLINE)
        url = factories.TestInstanceFactory.get_url(vm)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)

    def test_vm_with_backend_id_scheduled_to_deletion(self):
        vm = factories.TestInstanceFactory(state=Resource.States.OFFLINE, backend_id=123)
        url = factories.TestInstanceFactory.get_url(vm)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
