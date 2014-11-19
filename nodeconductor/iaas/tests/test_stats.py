from django.core.urlresolvers import reverse
from rest_framework import test, status

from nodeconductor.cloud.tests import factories as cloud_factories
from nodeconductor.iaas.tests import factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


class CustomerStatsTest(test.APITransactionTestCase):

    def setUp(self):
        self.customer = structure_factories.CustomerFactory()
        self.other_customer = structure_factories.CustomerFactory()
        cloud = cloud_factories.CloudFactory(customer=self.customer)
        flavor = cloud_factories.FlavorFactory(cloud=cloud)

        self.staff = structure_factories.UserFactory(is_staff=True)
        self.admin = structure_factories.UserFactory()
        self.group_manager = structure_factories.UserFactory()
        self.owner = structure_factories.UserFactory()

        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)

        self.project_group = structure_factories.ProjectGroupFactory(customer=self.customer)
        self.admin_project = structure_factories.ProjectFactory(customer=self.customer)
        self.manager_project = structure_factories.ProjectFactory(customer=self.customer)
        self.other_customer_project = structure_factories.ProjectFactory(customer=self.other_customer)

        self.manager_project.project_groups.add(self.project_group)
        self.project_group.add_user(self.group_manager, structure_models.ProjectGroupRole.MANAGER)
        self.admin_project.add_user(self.admin, structure_models.ProjectRole.ADMINISTRATOR)

        self.manager_instances = factories.InstanceFactory.create_batch(2, project=self.manager_project, flavor=flavor)
        self.admins_instances = factories.InstanceFactory.create_batch(2, project=self.admin_project, flavor=flavor)

        self.url = reverse('stats_customer')

    def test_staff_receive_statistics_for_all_cuctomers(self):
        self.client.force_authenticate(self.staff)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = [
            {
                'name': self.customer.name,
                'projects': 2,
                'project_groups': 1,
                'instances': 4,
            },
            {
                'name': self.other_customer.name,
                'projects': 1,
                'project_groups': 0,
                'instances': 0,
            }
        ]
        self.assertItemsEqual(response.data, expected_result)

    def test_owner_receive_statistics_for_his_customer(self):
        self.client.force_authenticate(self.owner)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = [
            {
                'name': self.customer.name,
                'projects': 2,
                'project_groups': 1,
                'instances': 4,
            },
        ]
        self.assertItemsEqual(response.data, expected_result)

    def test_group_manager_receive_statistics_for_his_group(self):
        self.client.force_authenticate(self.group_manager)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = [
            {
                'name': self.customer.name,
                'projects': 1,
                'project_groups': 1,
                'instances': 2,
            },
        ]
        self.assertItemsEqual(response.data, expected_result)

    def test_admin_receive_statistics_for_his_project(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = [
            {
                'name': self.customer.name,
                'projects': 1,
                'project_groups': 0,
                'instances': 2,
            },
        ]
        self.assertItemsEqual(response.data, expected_result)
