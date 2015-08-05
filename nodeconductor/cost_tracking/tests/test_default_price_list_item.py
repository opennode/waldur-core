from ddt import ddt, data
from rest_framework import test, status

from nodeconductor.cost_tracking.tests import factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


@ddt
class DefaultPriceListItemListTest(test.APITransactionTestCase):

    def setUp(self):
        self.users = {
            'staff': structure_factories.UserFactory(username='staff', is_staff=True),
            'owner': structure_factories.UserFactory(username='owner'),
            'administrator': structure_factories.UserFactory(username='administrator'),
            'manager': structure_factories.UserFactory(username='manager'),
            'regular_user': structure_factories.UserFactory(username='regular_user'),
        }

        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.users['owner'], structure_models.CustomerRole.OWNER)
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project.add_user(self.users['administrator'], structure_models.ProjectRole.ADMINISTRATOR)
        self.project_group = structure_factories.ProjectGroupFactory(customer=self.customer)
        self.project_group.add_user(self.users['manager'], structure_models.ProjectGroupRole.MANAGER)
        self.project_group.projects.add(self.project)

        self.default_price_list_item = factories.DefaultPriceListItemFactory()

    @data('staff', 'owner', 'manager', 'regular_user', 'administrator')
    def test_user_with_access_to_service_can_see_services_price_list(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.get(factories.DefaultPriceListItemFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.default_price_list_item.uuid.hex, [el['uuid'] for el in response.data])
