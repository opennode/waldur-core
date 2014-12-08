from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.iaas.tests import factories
from nodeconductor.structure.models import CustomerRole, ProjectRole, ProjectGroupRole
from nodeconductor.structure.tests import factories as structure_factories


class UrlResolverMixin(object):
    def _get_customer_url(self, customer):
        return 'http://testserver' + reverse('customer-detail', kwargs={'uuid': customer.uuid})

    def _get_cloud_url(self, cloud):
        return 'http://testserver' + reverse('cloud-detail', kwargs={'uuid': cloud.uuid})


class CustomerAddendumApiPermissionTest(UrlResolverMixin, test.APITransactionTestCase):
    def setUp(self):
        self.users = {
            'owner': structure_factories.UserFactory(),
            'admin': structure_factories.UserFactory(),
            'manager': structure_factories.UserFactory(),
            'group_manager': structure_factories.UserFactory(),
        }

        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.users['owner'], CustomerRole.OWNER)

        self.clouds = {
            'admin': factories.CloudFactory(customer=self.customer),
            'manager': factories.CloudFactory(customer=self.customer),
            'group_manager': factories.CloudFactory(customer=self.customer),
        }

        self.projects = {
            'admin': structure_factories.ProjectFactory(customer=self.customer),
            'manager': structure_factories.ProjectFactory(customer=self.customer),
            'group_manager': structure_factories.ProjectFactory(customer=self.customer)
        }

        self.projects['admin'].add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)
        self.projects['manager'].add_user(self.users['manager'], ProjectRole.MANAGER)
        project_group = structure_factories.ProjectGroupFactory(customer=self.customer)
        project_group.projects.add(self.projects['group_manager'])
        project_group.add_user(self.users['group_manager'], ProjectGroupRole.MANAGER)

        factories.CloudProjectMembershipFactory(project=self.projects['admin'], cloud=self.clouds['admin'])
        factories.CloudProjectMembershipFactory(project=self.projects['manager'], cloud=self.clouds['manager'])
        factories.CloudProjectMembershipFactory(
            project=self.projects['group_manager'], cloud=self.clouds['group_manager'])

    # Nested objects filtration tests
    def test_user_can_see_cloud_he_has_access_to_within_customer(self):
        for user_role in ('admin', 'manager', 'group_manager'):
            self.client.force_authenticate(user=self.users[user_role])

            seen_cloud = self.clouds[user_role]

            response = self.client.get(self._get_customer_url(self.customer))
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            self.assertIn('clouds', response.data, 'Customer must contain cloud list')

            cloud_urls = set([cloud['url'] for cloud in response.data['clouds']])
            self.assertIn(
                self._get_cloud_url(seen_cloud), cloud_urls,
                'User should see cloud',
            )

    def test_user_can_not_see_cloud_he_has_no_access_to_within_customer(self):
        for user_role, cloud in (
                ('admin', 'manager'),
                ('manager', 'admin'),
        ):
            self.client.force_authenticate(user=self.users[user_role])

            unseen_cloud = self.clouds[cloud]

            response = self.client.get(self._get_customer_url(self.customer))
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            cloud_urls = set([cloud['url'] for cloud in response.data['clouds']])
            self.assertNotIn(
                self._get_cloud_url(unseen_cloud), cloud_urls,
                'User should not see cloud',
            )

    def test_group_manger_can_see_all_clouds_of_customer(self):
        self.client.force_authenticate(user=self.users['group_manager'])
        seen_clouds = self.clouds.values()

        response = self.client.get(self._get_customer_url(self.customer))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertIn('clouds', response.data, 'Customer must contain cloud list')
        cloud_urls = set([cloud['url'] for cloud in response.data['clouds']])
        for seen_cloud in seen_clouds:
            self.assertIn(
                self._get_cloud_url(seen_cloud), cloud_urls,
                'Group manager should see all customer clouds',
            )

    # Helper methods
    def _check_user_list_access_customers(self, customers, test_function):
        response = self.client.get(reverse('customer-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        urls = set([instance['url'] for instance in response.data])
        for customer in customers:
            url = self._get_customer_url(customer)

            getattr(self, test_function)(url, urls)

    def _check_customer_in_list(self, customer, positive=True):
        response = self.client.get(reverse('customer-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        urls = set([instance['url'] for instance in response.data])
        customer_url = self._get_customer_url(customer)
        if positive:
            self.assertIn(customer_url, urls)
        else:
            self.assertNotIn(customer_url, urls)

    def _check_user_direct_access_customer(self, customers, status_code):
        for customer in customers:
            response = self.client.get(self._get_customer_url(customer))

            self.assertEqual(response.status_code, status_code)
