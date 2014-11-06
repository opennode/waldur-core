from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.cloud.tests import factories
from nodeconductor.structure.models import ProjectRole, CustomerRole, ProjectGroupRole
from nodeconductor.structure.tests import factories as structure_factories


class CloudPermissionTest(test.APITransactionTestCase):
    def setUp(self):
        self.customers = {
            'owned': structure_factories.CustomerFactory(),
            'has_admined_project': structure_factories.CustomerFactory(),
            'has_managed_project': structure_factories.CustomerFactory(),
            'has_managed_by_group_manager': structure_factories.CustomerFactory(),
        }

        self.users = {
            'customer_owner': structure_factories.UserFactory(),
            'project_admin': structure_factories.UserFactory(),
            'project_manager': structure_factories.UserFactory(),
            'group_manager': structure_factories.UserFactory(),
            'no_role': structure_factories.UserFactory(),
        }

        self.projects = {
            'owned': structure_factories.ProjectFactory(customer=self.customers['owned']),
            'admined': structure_factories.ProjectFactory(customer=self.customers['has_admined_project']),
            'managed': structure_factories.ProjectFactory(customer=self.customers['has_managed_project']),
            'managed_by_group_manager': structure_factories.ProjectFactory(
                customer=self.customers['has_managed_by_group_manager']),
        }

        self.clouds = {
            'owned': factories.CloudFactory(customer=self.customers['owned']),
            'admined': factories.CloudFactory(customer=self.customers['has_admined_project']),
            'managed': factories.CloudFactory(customer=self.customers['has_managed_project']),
            'managed_by_group_manager': factories.CloudFactory(
                customer=self.customers['has_managed_by_group_manager']),
            'not_in_project': factories.CloudFactory(),
        }

        self.customers['owned'].add_user(self.users['customer_owner'], CustomerRole.OWNER)

        self.projects['admined'].add_user(self.users['project_admin'], ProjectRole.ADMINISTRATOR)
        self.projects['managed'].add_user(self.users['project_manager'], ProjectRole.MANAGER)
        project_group = structure_factories.ProjectGroupFactory()
        project_group.projects.add(self.projects['managed_by_group_manager'])
        project_group.add_user(self.users['group_manager'], ProjectGroupRole.MANAGER)

        factories.CloudProjectMembershipFactory(cloud=self.clouds['admined'], project=self.projects['admined'])
        factories.CloudProjectMembershipFactory(cloud=self.clouds['managed'], project=self.projects['managed'])
        factories.CloudProjectMembershipFactory(
            cloud=self.clouds['managed_by_group_manager'], project=self.projects['managed_by_group_manager'])

        self.cloud_list_url = reverse('cloud-list')

    # List filtration tests
    def test_anonymous_user_cannot_list_clouds(self):
        response = self.client.get(self.cloud_list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_list_clouds_of_projects_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.users['project_admin'])

        response = self.client.get(self.cloud_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        cloud_url = self._get_cloud_url(self.clouds['admined'])
        self.assertIn(cloud_url, [instance['url'] for instance in response.data])

    def test_user_can_list_clouds_of_projects_he_is_manager_of(self):
        self.client.force_authenticate(user=self.users['project_manager'])

        response = self.client.get(self.cloud_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        cloud_url = self._get_cloud_url(self.clouds['managed'])
        self.assertIn(cloud_url, [instance['url'] for instance in response.data])

    def test_user_can_list_clouds_of_projects_he_is_group_manager_of(self):
        self.client.force_authenticate(user=self.users['group_manager'])

        response = self.client.get(self.cloud_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        cloud_url = self._get_cloud_url(self.clouds['managed_by_group_manager'])
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
        self.client.force_authenticate(user=self.users['no_role'])

        response = self.client.get(self.cloud_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for cloud_type in 'admined', 'managed', 'managed_by_group_manager':
            cloud_url = self._get_cloud_url(self.clouds[cloud_type])
            self.assertNotIn(
                cloud_url,
                [instance['url'] for instance in response.data],
                'User (role=none) should not see cloud (type=' + cloud_type + ')',
            )

    # Direct instance access tests
    def test_anonymous_user_cannot_access_cloud(self):
        for cloud_type in 'admined', 'managed', 'not_in_project':
            response = self.client.get(self._get_cloud_url(self.clouds[cloud_type]))
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_access_cloud_allowed_for_project_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.users['project_admin'])

        response = self.client.get(self._get_cloud_url(self.clouds['admined']))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_access_cloud_allowed_for_project_he_is_manager_of(self):
        self.client.force_authenticate(user=self.users['project_manager'])

        response = self.client.get(self._get_cloud_url(self.clouds['managed']))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_access_cloud_allowed_for_project_he_is_group_manager_of(self):
        self.client.force_authenticate(user=self.users['group_manager'])

        response = self.client.get(self._get_cloud_url(self.clouds['managed_by_group_manager']))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_see_clouds_customer_name(self):
        self.client.force_authenticate(user=self.users['project_admin'])

        response = self.client.get(self._get_cloud_url(self.clouds['admined']))

        customer = self.clouds['admined'].customer

        self.assertIn('customer', response.data)
        self.assertEqual(self._get_custmer_url(customer), response.data['customer'])

        self.assertIn('customer_name', response.data)
        self.assertEqual(customer.name, response.data['customer_name'])

    def test_user_cannot_access_cloud_allowed_for_project_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.users['no_role'])

        for cloud_type in 'admined', 'managed':
            response = self.client.get(self._get_cloud_url(self.clouds[cloud_type]))
            # 404 is used instead of 403 to hide the fact that the resource exists at all
            self.assertEqual(
                response.status_code,
                status.HTTP_404_NOT_FOUND,
                'User (role=none) should not see cloud (type=' + cloud_type + ')',
            )

    def test_user_cannot_access_cloud_not_allowed_for_any_project(self):
        for user_role in 'customer_owner', 'project_admin', 'project_manager', 'group_manager':
            self.client.force_authenticate(user=self.users[user_role])

            response = self.client.get(self._get_cloud_url(self.clouds['not_in_project']))
            # 404 is used instead of 403 to hide the fact that the resource exists at all
            self.assertEqual(
                response.status_code,
                status.HTTP_404_NOT_FOUND,
                'User (role=' + user_role + ') should not see cloud (type=not_in_project)',
            )

    # Nested objects filtration tests
    def test_user_can_see_flavors_within_cloud(self):
        for user_role, cloud_type in {
                'project_admin': 'admined',
                'project_manager': 'managed',
                'group_manager': 'managed_by_group_manager',
                }.iteritems():
            self.client.force_authenticate(user=self.users[user_role])

            seen_flavor = factories.FlavorFactory(cloud=self.clouds[cloud_type])

            response = self.client.get(self._get_cloud_url(self.clouds[cloud_type]))
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            self.assertIn(
                'flavors',
                response.data,
                'Cloud (type=' + cloud_type + ') must contain flavor list',
            )

            flavor_urls = set([flavor['url'] for flavor in response.data['flavors']])
            self.assertIn(
                self._get_flavor_url(seen_flavor),
                flavor_urls,
                'User (role=' + user_role + ') should see flavor',
            )

    # Creation tests
    def test_user_can_add_cloud_to_the_customer_he_owns(self):
        self.client.force_authenticate(user=self.users['customer_owner'])

        new_cloud = factories.CloudFactory.build(customer=self.customers['owned'])
        response = self.client.post(self.cloud_list_url, self._get_valid_payload(new_cloud))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_user_cannot_add_cloud_to_the_customer_he_sees_but_doesnt_own(self):
        for user_role, customer_type in {
                'project_admin': 'has_admined_project',
                'project_manager': 'has_managed_project',
            }.iteritems():
            self.client.force_authenticate(user=self.users[user_role])

            new_cloud = factories.CloudFactory.build(customer=self.customers[customer_type])
            response = self.client.post(self.cloud_list_url, self._get_valid_payload(new_cloud))
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_cannot_add_cloud_to_the_customer_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.users['no_role'])

        new_cloud = factories.CloudFactory.build(customer=self.customers['owned'])
        response = self.client.post(self.cloud_list_url, self._get_valid_payload(new_cloud))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # OpenStack backend related tests
    def test_user_cannot_create_cloud_with_auth_url_not_listed_in_settings(self):
        self.client.force_authenticate(user=self.users['customer_owner'])

        new_cloud = factories.CloudFactory.build(customer=self.customers['owned'])
        payload = self._get_valid_payload(new_cloud)
        payload['auth_url'] = 'http://another.example.com'

        response = self.client.post(self.cloud_list_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset(
            {'auth_url': ['http://another.example.com is not a known OpenStack deployment.']}, response.data)

    def test_user_can_create_cloud_with_auth_url_listed_in_settings(self):
        self.client.force_authenticate(user=self.users['customer_owner'])
        new_cloud = factories.CloudFactory.build(customer=self.customers['owned'])
        response = self.client.post(self.cloud_list_url, self._get_valid_payload(new_cloud))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

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
            'auth_url': 'http://example.com:5000/v2',
        }
