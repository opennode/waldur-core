from rest_framework import status
from rest_framework import test
from rest_framework.reverse import reverse

from nodeconductor.iaas.tests import factories as iaas_factories
from nodeconductor.structure import models


class PurchaseApiPermissionTest(test.APISimpleTestCase):
    def setUp(self):
        self.purchases = iaas_factories.PurchaseFactory.create_batch(3)

        self.purchases[0].project.add_user(self.purchases[0].user,
                                           models.Role.ADMINISTRATOR)
        self.purchases[1].project.add_user(self.purchases[1].user,
                                           models.Role.MANAGER)

    def test_user_can_list_purchase_history_of_project_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.purchases[0].user)

        response = self.client.get(reverse('purchase-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        purchase_url = self._get_purchase_url(self.purchases[0])
        self.assertIn(purchase_url, [purchase['url'] for purchase in response.data])

    def test_user_can_list_purchase_history_of_project_he_is_manager_of(self):
        self.client.force_authenticate(user=self.purchases[1].user)

        response = self.client.get(reverse('purchase-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        purchase_url = self._get_purchase_url(self.purchases[1])
        self.assertIn(purchase_url, [purchase['url'] for purchase in response.data])

    def test_user_cannot_list_purchase_history_of_project_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.purchases[2].user)

        response = self.client.get(reverse('purchase-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        purchase_url = self._get_purchase_url(self.purchases[0])
        self.assertNotIn(purchase_url, [purchase['url'] for purchase in response.data])

        purchase_url = self._get_purchase_url(self.purchases[1])
        self.assertNotIn(purchase_url, [purchase['url'] for purchase in response.data])

    # Helper methods
    def _get_purchase_url(self, purchase):
        return 'http://testserver' + reverse('purchase-detail', kwargs={'uuid': purchase.uuid})