from ddt import ddt, data
from rest_framework import status

from nodeconductor.structure.tests import factories as structure_factories

from . import factories
from .base_test import BaseCostTrackingTest


@ddt
class DefaultPriceListItemListTest(BaseCostTrackingTest):

    def setUp(self):
        super(DefaultPriceListItemListTest, self).setUp()
        self.users['regular_user'] = structure_factories.UserFactory(username='regular_user')
        self.default_price_list_item = factories.DefaultPriceListItemFactory()

    @data('staff', 'owner', 'manager', 'regular_user', 'administrator')
    def test_user_with_access_to_service_can_see_services_price_list(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.get(factories.DefaultPriceListItemFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.default_price_list_item.uuid.hex, [el['uuid'] for el in response.data])
