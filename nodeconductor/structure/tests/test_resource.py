import unittest

from rest_framework import test, status

from nodeconductor.structure.models import Resource
from nodeconductor.structure.tests import factories


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
