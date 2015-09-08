from ddt import ddt, data
from rest_framework import test, status

from nodeconductor.cost_tracking import models
from nodeconductor.cost_tracking.tests import factories
# dependency from openstack application exists only in tests
from nodeconductor.openstack.tests import factories as openstack_factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


@ddt
class PriceEstimateListTest(test.APITransactionTestCase):

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

        cloud = openstack_factories.OpenStackServiceFactory(customer=self.customer)
        self.service_project_link = openstack_factories.OpenStackServiceProjectLinkFactory(project=self.project, cloud=cloud)

        self.link_price_estimate = factories.PriceEstimateFactory(
            year=2012, month=10, scope=self.service_project_link, is_manually_input=True)
        self.project_price_estimate = factories.PriceEstimateFactory(scope=self.project, year=2015, month=7)

    @data('owner', 'manager', 'administrator')
    def test_user_can_see_price_estimate_for_his_project(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.get(factories.PriceEstimateFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.project_price_estimate.uuid.hex, [obj['uuid'] for obj in response.data])

    @data('owner', 'manager', 'administrator')
    def test_user_cannot_see_price_estimate_for_not_his_project(self, user):
        other_price_estimate = factories.PriceEstimateFactory()

        self.client.force_authenticate(self.users[user])
        response = self.client.get(factories.PriceEstimateFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(other_price_estimate.uuid.hex, [obj['uuid'] for obj in response.data])

    def test_user_can_filter_price_estimate_by_scope(self):
        self.client.force_authenticate(self.users['owner'])
        response = self.client.get(
            factories.PriceEstimateFactory.get_list_url(),
            data={'scope': structure_factories.ProjectFactory.get_url(self.project)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['uuid'], self.project_price_estimate.uuid.hex)

    def test_user_can_filter_price_estimates_by_date(self):
        self.client.force_authenticate(self.users['administrator'])
        response = self.client.get(
            factories.PriceEstimateFactory.get_list_url(),
            data={'date': '{}.{}'.format(self.link_price_estimate.year, self.link_price_estimate.month)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['uuid'], self.link_price_estimate.uuid.hex)

    def test_user_can_filter_price_estimates_by_date_range(self):
        self.client.force_authenticate(self.users['manager'])
        response = self.client.get(
            factories.PriceEstimateFactory.get_list_url(),
            data={'start': '{}.{}'.format(self.link_price_estimate.year, self.link_price_estimate.month+1),
                  'end': '{}.{}'.format(self.project_price_estimate.year, self.project_price_estimate.month+1)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['uuid'], self.project_price_estimate.uuid.hex)


@ddt
class PriceEstimateCreateTest(test.APITransactionTestCase):

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
        self.service_project_link = openstack_factories.OpenStackServiceProjectLinkFactory(
            project=self.project, service=self.service)

        self.valid_data = {
            'scope': openstack_factories.OpenStackServiceProjectLinkFactory.get_url(self.service_project_link),
            'total': 100,
            'details': {'ram': 50, 'disk': 50},
            'month': 7,
            'year': 2015,
        }

    @data('owner', 'staff')
    def test_user_can_create_price_estimate(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.post(factories.PriceEstimateFactory.get_list_url(), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(models.PriceEstimate.objects.filter(
            scope=self.service_project_link,
            is_manually_input=True,
            month=self.valid_data['month'],
            year=self.valid_data['year'],
            is_visible=True).exists()
        )

    @data('manager', 'administrator')
    def test_user_without_permissions_can_not_create_price_estimate(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.post(factories.PriceEstimateFactory.get_list_url(), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @data('owner', 'staff', 'manager', 'administrator')
    def test_user_cannot_create_price_estimate_for_project(self, user):
        self.valid_data['scope'] = structure_factories.ProjectFactory.get_url(self.project)

        self.client.force_authenticate(self.users[user])
        response = self.client.post(factories.PriceEstimateFactory.get_list_url(), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manually_inputed_price_estimate_replaces_autocalcuted(self):
        price_estimate = factories.PriceEstimateFactory(
            scope=self.service_project_link, month=self.valid_data['month'], year=self.valid_data['year'])

        self.client.force_authenticate(self.users['owner'])
        response = self.client.post(factories.PriceEstimateFactory.get_list_url(), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        reread_price_estimate = models.PriceEstimate.objects.get(id=price_estimate.id)
        self.assertFalse(reread_price_estimate.is_visible)


class PriceEstimateUpdateTest(test.APITransactionTestCase):

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

        cloud = openstack_factories.OpenStackServiceFactory(customer=self.customer)
        self.service_project_link = openstack_factories.OpenStackServiceProjectLinkFactory(project=self.project, cloud=cloud)

        self.price_estimate = factories.PriceEstimateFactory(scope=self.service_project_link)
        self.valid_data = {
            'scope': openstack_factories.OpenStackServiceProjectLinkFactory.get_url(self.service_project_link),
            'total': 100,
            'details': {'ram': 50, 'disk': 50},
            'month': 7,
            'year': 2015,
        }

    def test_price_estimate_scope_cannot_be_updated(self):
        other_service_project_link = openstack_factories.OpenStackServiceProjectLinkFactory(project=self.project)
        self.valid_data['scope'] = openstack_factories.OpenStackServiceProjectLinkFactory.get_url(
            other_service_project_link)

        self.client.force_authenticate(self.users['staff'])
        response = self.client.patch(factories.PriceEstimateFactory.get_url(self.price_estimate), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        reread_price_estimate = models.PriceEstimate.objects.get(id=self.price_estimate.id)
        self.assertNotEqual(reread_price_estimate.scope, other_service_project_link)

    def test_autocalculated_estimate_cannot_be_manually_updated(self):
        self.client.force_authenticate(self.users['staff'])
        response = self.client.patch(factories.PriceEstimateFactory.get_url(self.price_estimate), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        reread_price_estimate = models.PriceEstimate.objects.get(id=self.price_estimate.id)
        self.assertFalse(reread_price_estimate.is_manually_input)


class PriceEstimateDeleteTest(test.APITransactionTestCase):

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

        cloud = openstack_factories.OpenStackServiceFactory(customer=self.customer)
        self.service_project_link = openstack_factories.OpenStackServiceProjectLinkFactory(project=self.project, cloud=cloud)

        self.manual_link_price_estimate = factories.PriceEstimateFactory(
            scope=self.service_project_link, is_manually_input=True)
        self.auto_link_price_estimate = factories.PriceEstimateFactory(
            scope=self.service_project_link, is_manually_input=False,
            month=self.manual_link_price_estimate.month, year=self.manual_link_price_estimate.year)
        self.project_price_estimate = factories.PriceEstimateFactory(scope=self.project)

    def test_autocreated_price_estimate_cannot_be_deleted(self):
        self.client.force_authenticate(self.users['staff'])
        response = self.client.delete(factories.PriceEstimateFactory.get_url(self.project_price_estimate))

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_autocreated_price_estimate_become_visible_on_manual_estimate_deletion(self):
        self.client.force_authenticate(self.users['staff'])
        response = self.client.delete(factories.PriceEstimateFactory.get_url(self.manual_link_price_estimate))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        reread_auto_link_price_estimate = models.PriceEstimate.objects.get(id=self.auto_link_price_estimate.id)
        self.assertTrue(reread_auto_link_price_estimate.is_visible)
