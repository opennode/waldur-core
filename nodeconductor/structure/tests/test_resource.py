from rest_framework import test, status

from nodeconductor.structure.models import Resource, NewResource, ServiceSettings
from nodeconductor.structure.tests import factories, models as test_models


class ResourceRemovalTest(test.APITransactionTestCase):
    def setUp(self):
        self.user = factories.UserFactory(is_staff=True)
        self.client.force_authenticate(user=self.user)

    def test_vm_unlinked_immediately_anyway(self):
        vm = factories.TestInstanceFactory(state=Resource.States.PROVISIONING_SCHEDULED)
        url = factories.TestInstanceFactory.get_url(vm, 'unlink')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)

    def test_new_resource_unlinked_immediately(self):
        vm = factories.TestNewInstanceFactory(state=NewResource.States.OK)
        url = factories.TestNewInstanceFactory.get_url(vm, 'unlink')
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

    def test_when_virtual_machine_is_deleted_descendant_resources_unlinked(self):
        # Arrange
        vm = factories.TestInstanceFactory()
        settings = factories.ServiceSettingsFactory(scope=vm)
        service = factories.TestServiceFactory(settings=settings)
        link = factories.TestServiceProjectLinkFactory(service=service)
        child_vm = factories.TestInstanceFactory(service_project_link=link)
        other_vm = factories.TestInstanceFactory()

        # Act
        vm.delete()

        # Assert
        self.assertFalse(test_models.TestInstance.objects.filter(id=child_vm.id).exists())
        self.assertFalse(test_models.TestService.objects.filter(id=service.id).exists())
        self.assertFalse(ServiceSettings.objects.filter(id=settings.id).exists())
        self.assertTrue(test_models.TestInstance.objects.filter(id=other_vm.id).exists())


class ResourceCreateTest(test.APITransactionTestCase):

    def setUp(self):
        self.user = factories.UserFactory(is_staff=True)
        self.client.force_authenticate(user=self.user)
        self.service_project_link = factories.TestServiceProjectLinkFactory()

    def test_resource_cannot_be_created_for_invalid_service(self):
        self.service_project_link.project.certifications.add(factories.ServiceCertificationFactory())
        self.assertFalse(self.service_project_link.is_valid)
        payload = {
            'service_project_link': factories.TestServiceProjectLinkFactory.get_url(self.service_project_link),
            'name': 'impossible resource',
        }
        url = factories.TestInstanceFactory.get_list_url()

        response = self.client.post(url, payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('service_project_link', response.data)

