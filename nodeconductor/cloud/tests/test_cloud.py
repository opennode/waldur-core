from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.cloud.tests import factories as factories
from nodeconductor.structure.models import ProjectRole, CustomerRole
from nodeconductor.structure.tests import factories as structure_factories


class CloudPermissionTest(test.APITransactionTestCase):
    def setUp(self):
        self.customers = {}
        for customer_type in 'owned', :
            self.customers[customer_type] = structure_factories.CustomerFactory()

        self.users = {}
        for user_type in 'customer_owner', 'project_admin', 'no_role':
            self.users[user_type] = structure_factories.UserFactory()

        self.projects = {}
        for project_type in 'owned', :
            self.projects[project_type] = structure_factories.ProjectFactory()

        self.cloud_resources = {}
        for cloud_type in 'owned', :
            self.cloud_resources[cloud_type] = factories.CloudFactory.build()

        self.customers['owned'].add_user(self.users['customer_owner'], CustomerRole.OWNER)
        self.projects['owned'].customer = self.customers['owned']
        self.cloud_resources['owned'].customer = self.customers['owned']

        # Deprecated

        self.user = structure_factories.UserFactory.create()

        admined_project = structure_factories.ProjectFactory()
        managed_project = structure_factories.ProjectFactory()

        admined_project.add_user(self.user, ProjectRole.ADMINISTRATOR)
        managed_project.add_user(self.user, ProjectRole.MANAGER)

        self.admined_cloud = factories.CloudFactory()
        self.managed_cloud = factories.CloudFactory()

        admined_project.clouds.add(self.admined_cloud)
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

    def test_user_can_add_cloud_to_the_customer_he_owns(self):
        self.client.force_authenticate(user=self.users['customer_owner'])

        response = self.client.post(reverse('cloud-list'), self._get_valid_payload(self.cloud_resources['owned']))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

#    def test_user_cannot_add_cloud_to_the_customer_he_doesnt_own(self):
#        self.client.force_authenticate(user=self.users['project_admin'])
#
#        response = self.client.post(reverse('cloud-list'), self._get_valid_payload(self.cloud_resources['owned']))
#        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
#        self.assertDictContainsSubset({'customer': ['Invalid hyperlink - object does not exist.']}, response.data)

#    def test_user_cannot_add_cloud_to_the_customer_he_has_no_role_in(self):
#        self.client.force_authenticate(user=self.users['no_role'])
#
#        response = self.client.post(reverse('cloud-list'), self._get_valid_payload(self.cloud_resources['owned']))
#        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def _get_cloud_url(self, cloud):
        return 'http://testserver' + reverse('cloud-detail', kwargs={'uuid': cloud.uuid})

    def _get_valid_payload(self, resource):
        return {
            'name': resource.name,
            'customer': 'http://testserver' + reverse('customer-detail', kwargs={'uuid': resource.customer.uuid}),
        }
