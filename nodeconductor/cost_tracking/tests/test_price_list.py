from ddt import ddt, data
from rest_framework import test, status

from nodeconductor.cost_tracking import models
from nodeconductor.cost_tracking.tests import factories
from nodeconductor.oracle.tests import factories as oracle_factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


@ddt
class PriceListListTest(test.APITransactionTestCase):

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

        self.service = oracle_factories.OracleServiceFactory(customer=self.customer)
        self.price_list = factories.PriceListFactory(service=self.service)

    @data('staff', 'owner', 'manager')
    def test_user_with_access_to_service_can_see_services_price_list(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.get(factories.PriceListFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.price_list.uuid.hex, [el['uuid'] for el in response.data])

    @data('administrator')
    def test_user_without_access_to_service_cannot_see_services_price_list(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.get(factories.PriceListFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.price_list.uuid.hex, [el['uuid'] for el in response.data])

    def test_price_list_can_be_filtered_by_service(self):
        other_price_list = factories.PriceListFactory()

        self.client.force_authenticate(self.users['staff'])
        response = self.client.get(
            factories.PriceListFactory.get_list_url(),
            data={'service': oracle_factories.OracleServiceFactory.get_url(self.service)}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.price_list.uuid.hex, [el['uuid'] for el in response.data])
        self.assertNotIn(other_price_list.uuid.hex, [el['uuid'] for el in response.data])


@ddt
class PriceListCreateTest(test.APITransactionTestCase):

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

        self.service = oracle_factories.OracleServiceFactory(customer=self.customer)
        self.valid_data = {
            'service': oracle_factories.OracleServiceFactory.get_url(self.service),
            'items': [
                {'name': 'cpu', 'value': 1000, 'units': 'USD per CPU'},
                {'name': 'ram', 'value': 1000, 'units': 'GB/H'},
            ]
        }

    @data('staff', 'owner')
    def test_user_with_permissions_can_create_service_with_valid_data(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.post(factories.PriceListFactory.get_list_url(), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(models.PriceList.objects.filter(service=self.service).exists())
        self.assertEqual(models.PriceList.objects.filter(service=self.service)[0].items.count(), 2)

    @data('administrator', 'manager')
    def test_user_without_permissions_cannot_create_price_list(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.post(factories.PriceListFactory.get_list_url(), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(models.PriceList.objects.filter(service=self.service).exists())

    def test_service_cannot_have_more_then_one_price_list(self):
        factories.PriceListFactory(service=self.service)

        self.client.force_authenticate(self.users['owner'])
        response = self.client.post(factories.PriceListFactory.get_list_url(), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(models.PriceList.objects.filter(service=self.service).count(), 1)


@ddt
class PriceListUpdateTest(test.APITransactionTestCase):

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

        self.service = oracle_factories.OracleServiceFactory(customer=self.customer)
        self.price_list = factories.PriceListFactory(service=self.service)

    @data('staff', 'owner')
    def test_user_with_permissions_can_update_price_list(self, user):
        self.client.force_authenticate(self.users[user])
        data = {'items': [{'name': 'cpu', 'value': 1000, 'units': 'USD per CPU'}, {'name': 'memory', 'value': 1000, 'units': 'USD per CPU'}]}
        response = self.client.patch(factories.PriceListFactory.get_url(self.price_list), data=data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.price_list.items.count(), 1)
        item = self.price_list.items.all()[0]
        for field, value in data['items'][0].items():
            self.assertEqual(getattr(item, field), value)

    # We do not execute this test for administrator, because he does not see price estimates at all
    @data('manager')
    def test_user_without_permissions_cannot_update_price_list(self, user):
        self.client.force_authenticate(self.users[user])
        data = {'items': [{'name': 'cpu', 'value': 1000, 'units': 'USD per CPU'}]}
        response = self.client.patch(factories.PriceListFactory.get_url(self.price_list), data=data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@ddt
class PriceListDeleteTest(test.APITransactionTestCase):

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

        self.service = oracle_factories.OracleServiceFactory(customer=self.customer)
        self.price_list = factories.PriceListFactory(service=self.service)

    @data('staff', 'owner')
    def test_user_with_permissions_can_delete_price_list(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.delete(factories.PriceListFactory.get_url(self.price_list))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(models.PriceList.objects.filter(id=self.price_list.id).exists())

    # We do not execute this test for administrator, because he does not see price estimates at all
    @data('manager')
    def test_user_without_permissions_cannot_delete_price_list(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.delete(factories.PriceListFactory.get_url(self.price_list))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(models.PriceList.objects.filter(id=self.price_list.id).exists())
