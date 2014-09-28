from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.cloud.tests import factories
from nodeconductor.structure.models import ProjectRole, CustomerRole
from nodeconductor.structure.tests import factories as structure_factories


class CloudPermissionTest(test.APITransactionTestCase):
    def setUp(self):
        self.customers = {
            'owned': structure_factories.CustomerFactory(),
            'project_admin': structure_factories.CustomerFactory(),
        }

        self.users = {
            'customer_owner': structure_factories.UserFactory(),
            'project_admin': structure_factories.UserFactory(),
            'no_role': structure_factories.UserFactory(),
        }

        self.projects = {
            'owned': structure_factories.ProjectFactory(customer=self.customers['owned']),
            'project_admin': structure_factories.ProjectFactory(customer=self.customers['project_admin']),
        }

        self.clouds = {
            'owned': factories.CloudFactory.build(customer=self.customers['owned']),  # Note, not committed to db
            'project_admin': factories.CloudFactory(customer=self.customers['project_admin']),
        }

        self.customers['owned'].add_user(self.users['customer_owner'], CustomerRole.OWNER)

        self.projects['project_admin'].add_user(self.users['project_admin'], ProjectRole.ADMINISTRATOR)
        # Deprecated

        self.user = structure_factories.UserFactory.create()

        managed_project = structure_factories.ProjectFactory()

        self.projects['project_admin'].add_user(self.user, ProjectRole.ADMINISTRATOR)
        managed_project.add_user(self.user, ProjectRole.MANAGER)

        self.admined_cloud = self.clouds['project_admin']
        self.managed_cloud = factories.CloudFactory()

        self.projects['project_admin'].clouds.add(self.admined_cloud)
        managed_project.clouds.add(self.managed_cloud)

    # List filtration tests
    def test_anonymous_user_cannot_list_clouds(self):
        response = self.client.get(reverse('cloud-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_list_clouds_of_projects_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('cloud-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        cloud_url = self._get_cloud_url(self.admined_cloud)
        self.assertIn(cloud_url, [instance['url'] for instance in response.data])

    def test_user_can_list_clouds_of_projects_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('cloud-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        cloud_url = self._get_cloud_url(self.managed_cloud)
        self.assertIn(cloud_url, [instance['url'] for instance in response.data])

    def test_user_can_list_clouds_of_projects_he_is_customer_owner_of(self):
        # persist affected objects
        self.clouds['owned'].save()  # make sure that cloud gets a UUID
        self.customers['owned'].save()  # make sure that customer link is saved

        self.client.force_authenticate(user=self.users['customer_owner'])

        response = self.client.get(reverse('cloud-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        cloud_url = self._get_cloud_url(self.clouds['owned'])
        self.assertIn(cloud_url, [instance['url'] for instance in response.data])

    def test_user_cannot_list_clouds_of_projects_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.user)

        inaccessible_cloud = factories.CloudFactory()

        response = self.client.get(reverse('cloud-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        cloud_url = self._get_cloud_url(inaccessible_cloud)
        self.assertNotIn(cloud_url, [instance['url'] for instance in response.data])

    # Direct instance access tests
    def test_anonymous_user_cannot_access_cloud(self):
        cloud = factories.CloudFactory()
        response = self.client.get(self._get_cloud_url(cloud))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_access_cloud_allowed_for_project_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self._get_cloud_url(self.admined_cloud))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_access_cloud_allowed_for_project_he_is_manager_of(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self._get_cloud_url(self.managed_cloud))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_see_clouds_customer_name(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self._get_cloud_url(self.admined_cloud))

        customer = self.admined_cloud.customer

        self.assertIn('customer', response.data)
        self.assertEqual(self._get_custmer_url(customer), response.data['customer'])

        self.assertIn('customer_name', response.data)
        self.assertEqual(customer.name, response.data['customer_name'])

    def test_user_cannot_access_cloud_allowed_for_project_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.user)

        inaccessible_cloud = factories.CloudFactory()
        inaccessible_project = structure_factories.ProjectFactory()
        inaccessible_project.clouds.add(inaccessible_cloud)

        response = self.client.get(self._get_cloud_url(inaccessible_cloud))
        # 404 is used instead of 403 to hide the fact that the resource exists at all
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_access_cloud_not_allowed_for_any_project(self):
        self.client.force_authenticate(user=self.user)

        inaccessible_cloud = factories.CloudFactory()

        response = self.client.get(self._get_cloud_url(inaccessible_cloud))
        # 404 is used instead of 403 to hide the fact that the resource exists at all
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # Nested objects filtration tests
    def test_user_can_see_flavors_within_cloud(self):
        self.client.force_authenticate(user=self.users['project_admin'])

        cloud = self.clouds['project_admin']

        seen_flavor = factories.FlavorFactory(cloud=cloud)

        response = self.client.get(self._get_cloud_url(cloud))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertIn('flavors', response.data, 'Cloud must contain flavor list')

        flavor_urls = set([flavor['url'] for flavor in response.data['flavors']])
        self.assertIn(
            self._get_flavor_url(seen_flavor), flavor_urls,
            'User should see flavor',
        )

    # Creation tests
    def test_user_can_add_cloud_to_the_customer_he_owns(self):
        self.client.force_authenticate(user=self.users['customer_owner'])

        response = self.client.post(reverse('cloud-list'), self._get_valid_payload(self.clouds['owned']))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_user_cannot_add_cloud_to_the_customer_he_sees_but_doesnt_own(self):
        self.client.force_authenticate(user=self.users['project_admin'])

        cloud = factories.CloudFactory.build(customer=self.customers['project_admin'])
        response = self.client.post(reverse('cloud-list'), self._get_valid_payload(cloud))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_cannot_add_cloud_to_the_customer_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.users['no_role'])

        response = self.client.post(reverse('cloud-list'), self._get_valid_payload(self.clouds['owned']))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def _get_cloud_url(self, cloud):
        return 'http://testserver' + reverse('cloud-detail', kwargs={'uuid': cloud.uuid})

    def _get_flavor_url(self, flavor):
        return 'http://testserver' + reverse('flavor-detail', kwargs={'uuid': flavor.uuid})

    def _get_custmer_url(self, customer):
        return 'http://testserver' + reverse('customer-detail', kwargs={'uuid': customer.uuid})

    def _get_valid_payload(self, resource):
        return {
            'name': resource.name,
            'customer': 'http://testserver' + reverse('customer-detail', kwargs={'uuid': resource.customer.uuid}),
        }
