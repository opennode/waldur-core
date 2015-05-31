from rest_framework import test, status

from nodeconductor.logging.tests import factories
# Dependency from `structure` application exists only in tests
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


class AlertsListTest(test.APITransactionTestCase):

    def setUp(self):
        self.customer = structure_factories.CustomerFactory()
        self.owner = structure_factories.UserFactory()
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)

    def test_customer_owner_can_see_alert_about_his_customer(self):
        alert = factories.AlertFactory(scope=self.customer)

        self.client.force_authenticate(self.owner)
        response = self.client.get(factories.AlertFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(alert.uuid.hex, [a['uuid'] for a in response.data])

    def test_customer_owner_cannot_see_alert_about_other_customer(self):
        alert = factories.AlertFactory()

        self.client.force_authenticate(self.owner)
        response = self.client.get(factories.AlertFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(alert.uuid.hex, [a['uuid'] for a in response.data])
