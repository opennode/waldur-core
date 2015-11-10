from ddt import ddt, data
from rest_framework import test, status

from nodeconductor.cost_tracking import models
from nodeconductor.cost_tracking.tests import factories
from nodeconductor.openstack import models as openstack_models
from nodeconductor.openstack.tests import factories as openstack_factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


@ddt
class PriceListItemListTest(test.APITransactionTestCase):

    def setUp(self):
        self.users = {
            'staff': structure_factories.UserFactory(username='staff', is_staff=True),
            'owner': structure_factories.UserFactory(username='owner'),
            'administrator': structure_factories.UserFactory(username='administrator'),
            'manager': structure_factories.UserFactory(username='manager'),
        }

        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.users['owner'], structure_models.CustomerRole.OWNER)
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project.add_user(self.users['administrator'], structure_models.ProjectRole.ADMINISTRATOR)
        self.project_group = structure_factories.ProjectGroupFactory(customer=self.customer)
        self.project_group.add_user(self.users['manager'], structure_models.ProjectGroupRole.MANAGER)
        self.project_group.projects.add(self.project)

        self.service = openstack_factories.OpenStackServiceFactory(customer=self.customer)
        self.price_list_item = factories.PriceListItemFactory(service=self.service)

    @data('staff', 'owner', 'manager')
    def test_user_with_access_to_service_can_see_services_price_list(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.get(factories.PriceListItemFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.price_list_item.uuid.hex, [el['uuid'] for el in response.data])

    @data('administrator')
    def test_user_without_access_to_service_cannot_see_services_price_list(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.get(factories.PriceListItemFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.price_list_item.uuid.hex, [el['uuid'] for el in response.data])

    def test_price_list_can_be_filtered_by_service(self):
        other_price_list_item = factories.PriceListItemFactory()

        self.client.force_authenticate(self.users['staff'])
        response = self.client.get(
            factories.PriceListItemFactory.get_list_url(),
            data={'service': openstack_factories.OpenStackServiceFactory.get_url(self.service)}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.price_list_item.uuid.hex, [el['uuid'] for el in response.data])
        self.assertNotIn(other_price_list_item.uuid.hex, [el['uuid'] for el in response.data])


@ddt
class PriceListItemCreateTest(test.APITransactionTestCase):

    def setUp(self):
        self.users = {
            'staff': structure_factories.UserFactory(username='staff', is_staff=True),
            'owner': structure_factories.UserFactory(username='owner'),
            'administrator': structure_factories.UserFactory(username='administrator'),
            'manager': structure_factories.UserFactory(username='manager'),
        }

        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.users['owner'], structure_models.CustomerRole.OWNER)
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project.add_user(self.users['administrator'], structure_models.ProjectRole.ADMINISTRATOR)
        self.project_group = structure_factories.ProjectGroupFactory(customer=self.customer)
        self.project_group.add_user(self.users['manager'], structure_models.ProjectGroupRole.MANAGER)
        self.project_group.projects.add(self.project)

        self.service = openstack_factories.OpenStackServiceFactory(customer=self.customer)
        openstack_models.OpenStackServiceProjectLink.objects.create(project=self.project, service=self.service)
        self.valid_data = {
            'service': openstack_factories.OpenStackServiceFactory.get_url(self.service),
            'value': 100,
            'units': 'UAH',
            'key': 'test_key',
            'item_type': 'storage',
        }

    @data('staff', 'owner')
    def test_user_with_permissions_can_create_price_list_item(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.post(factories.PriceListItemFactory.get_list_url(), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(models.PriceListItem.objects.filter(
            service=self.service, value=self.valid_data['value'], item_type=self.valid_data['item_type']).exists())

    @data('manager', 'administrator')
    def test_user_without_permissions_cannot_create_price_list_item(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.post(factories.PriceListItemFactory.get_list_url(), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, str(response.data) + " " + user)
        self.assertFalse(models.PriceListItem.objects.filter(
            service=self.service, value=self.valid_data['value'], item_type=self.valid_data['item_type']).exists())


@ddt
class PriceListItemUpdateTest(test.APITransactionTestCase):

    def setUp(self):
        self.users = {
            'staff': structure_factories.UserFactory(username='staff', is_staff=True),
            'owner': structure_factories.UserFactory(username='owner'),
            'administrator': structure_factories.UserFactory(username='administrator'),
            'manager': structure_factories.UserFactory(username='manager'),
        }

        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.users['owner'], structure_models.CustomerRole.OWNER)
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project.add_user(self.users['administrator'], structure_models.ProjectRole.ADMINISTRATOR)
        self.project_group = structure_factories.ProjectGroupFactory(customer=self.customer)
        self.project_group.add_user(self.users['manager'], structure_models.ProjectGroupRole.MANAGER)
        self.project_group.projects.add(self.project)

        self.service = openstack_factories.OpenStackServiceFactory(customer=self.customer)
        self.price_list_item = factories.PriceListItemFactory(service=self.service)

    @data('staff', 'owner')
    def test_user_with_permissions_can_update_price_list_item(self, user):
        self.client.force_authenticate(self.users[user])
        data = {'value': 200}
        response = self.client.patch(factories.PriceListItemFactory.get_url(self.price_list_item), data=data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        reread_price_list_item = models.PriceListItem.objects.get(id=self.price_list_item.id)
        self.assertEqual(reread_price_list_item.value, data['value'])

    # We do not execute this test for administrator, because he does not see price estimates at all
    @data('manager')
    def test_user_without_permissions_cannot_update_price_list_item(self, user):
        self.client.force_authenticate(self.users[user])
        data = {'items': [{'name': 'cpu', 'value': 1000, 'units': 'USD per CPU'}]}
        response = self.client.patch(factories.PriceListItemFactory.get_url(self.price_list_item), data=data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
