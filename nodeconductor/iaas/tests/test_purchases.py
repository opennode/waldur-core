from rest_framework import status
from rest_framework import test
from rest_framework.reverse import reverse

from nodeconductor.iaas.tests import factories as iaas_factories
from nodeconductor.structure.models import Role
from nodeconductor.structure.tests import factories as structure_factories


class PurchaseApiPermissionTest(test.APISimpleTestCase):
    def setUp(self):
        self.user = structure_factories.UserFactory.create()
        self.client.force_authenticate(user=self.user)

        admined_project = structure_factories.ProjectFactory()
        managed_project = structure_factories.ProjectFactory()
        inaccessible_project = structure_factories.ProjectFactory()

        admined_project.add_user(self.user, Role.ADMINISTRATOR)
        managed_project.add_user(self.user, Role.MANAGER)

        self.admined_purchase = iaas_factories.PurchaseFactory(project=admined_project)
        self.managed_purchase = iaas_factories.PurchaseFactory(project=managed_project)
        self.inaccessible_purchase = iaas_factories.PurchaseFactory(project=inaccessible_project)

    # List filtration tests
    def test_user_can_list_purchase_history_of_project_he_is_administrator_of(self):
        response = self.client.get(reverse('purchase-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        purchase_url = self._get_purchase_url(self.admined_purchase)
        self.assertIn(purchase_url, [purchase['url'] for purchase in response.data])

    def test_user_can_list_purchase_history_of_project_he_is_manager_of(self):
        response = self.client.get(reverse('purchase-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        purchase_url = self._get_purchase_url(self.managed_purchase)
        self.assertIn(purchase_url, [purchase['url'] for purchase in response.data])

    def test_user_cannot_list_purchase_history_of_project_he_has_no_role_in(self):
        response = self.client.get(reverse('purchase-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        purchase_url = self._get_purchase_url(self.inaccessible_purchase)
        self.assertNotIn(purchase_url, [purchase['url'] for purchase in response.data])

    def test_user_cannot_list_purchases_not_allowed_for_any_project(self):
        inaccessible_purchase = iaas_factories.PurchaseFactory()

        response = self.client.get(reverse('purchase-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        purchase_url = self._get_purchase_url(inaccessible_purchase)
        self.assertNotIn(purchase_url, [instance['url'] for instance in response.data])

    # Direct purchase access tests
    def test_user_can_access_purchase_of_project_he_is_administrator_of(self):
        response = self.client.get(self._get_purchase_url(self.admined_purchase))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_access_purchase_of_project_he_is_manager_of(self):
        response = self.client.get(self._get_purchase_url(self.managed_purchase))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_access_purchase_of_project_he_has_no_role_in(self):
        response = self.client.get(self._get_purchase_url(self.inaccessible_purchase))
        # 404 is used instead of 403 to hide the fact that the resource exists at all
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_access_purchase_not_allowed_for_any_project(self):
        inaccessible_purchase = iaas_factories.PurchaseFactory()

        response = self.client.get(self._get_purchase_url(inaccessible_purchase))
        # 404 is used instead of 403 to hide the fact that the resource exists at all
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
    # Helper methods
    def _get_purchase_url(self, purchase):
        return 'http://testserver' + reverse('purchase-detail', kwargs={'uuid': purchase.uuid})


class PurchaseApiManipulationTest(test.APISimpleTestCase):
    def setUp(self):
        self.user = structure_factories.UserFactory.create()
        self.client.force_authenticate(user=self.user)

        self.purchase = iaas_factories.PurchaseFactory()
        self.purchase_url = 'http://testserver' + reverse('purchase-detail', kwargs={'uuid': self.purchase.uuid})

    def test_cannot_delete_purchase(self):
        response = self.client.delete(self.purchase_url)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_create_purchase(self):
        data = {
            'user': self.purchase.user.username,
            'date': self.purchase.date,
            'project': 'http://testserver' + reverse('project-detail',
                                                     kwargs={'uuid': structure_factories.ProjectFactory().uuid})
        }

        response = self.client.post(self.purchase_url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_change_purchase_as_whole(self):
        data = {
            'user': self.purchase.user.username,
            'date': self.purchase.date,
            'project': 'http://testserver' + reverse('project-detail',
                                                     kwargs={'uuid': self.purchase.project.uuid})
        }

        response = self.client.put(self.purchase_url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_change_single_purchase_field(self):
        data = {
            'date': self.purchase.date,
        }

        response = self.client.patch(self.purchase_url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
