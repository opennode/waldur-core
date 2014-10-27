from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.cloud.tests import factories
from nodeconductor.structure.models import ProjectRole
from nodeconductor.structure.tests import factories as structure_factories


class FlavorApiPermissionTest(test.APISimpleTestCase):
    forbidden_combinations = (
        # User role, Flavor
        ('admin', 'manager'),
        ('admin', 'inaccessible'),
        ('manager', 'admin'),
        ('manager', 'inaccessible'),
        ('no_role', 'admin'),
        ('no_role', 'manager'),
        ('no_role', 'inaccessible'),
    )

    def setUp(self):
        self.users = {
            'admin': structure_factories.UserFactory(),
            'manager': structure_factories.UserFactory(),
            'no_role': structure_factories.UserFactory(),
        }

        self.flavors = {
            'admin': factories.FlavorFactory(),
            'manager': factories.FlavorFactory(),
            'inaccessible': factories.FlavorFactory(),
        }

        admined_project = structure_factories.ProjectFactory()
        managed_project = structure_factories.ProjectFactory()

        admined_project.add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)
        managed_project.add_user(self.users['manager'], ProjectRole.MANAGER)

        factories.CloudProjectMembershipFactory(cloud=self.flavors['admin'].cloud, project=admined_project)
        factories.CloudProjectMembershipFactory(cloud=self.flavors['manager'].cloud, project=managed_project)

    # List filtration tests
    def test_anonymous_user_cannot_list_flavors(self):
        response = self.client.get(reverse('flavor-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_list_flavors_of_projects_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.users['admin'])

        response = self.client.get(reverse('flavor-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        flavor_url = self._get_flavor_url(self.flavors['admin'])
        self.assertIn(flavor_url, [instance['url'] for instance in response.data])

    def test_user_can_list_flavors_of_projects_he_is_manager_of(self):
        self.client.force_authenticate(user=self.users['manager'])

        response = self.client.get(reverse('flavor-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        flavor_url = self._get_flavor_url(self.flavors['manager'])
        self.assertIn(flavor_url, [instance['url'] for instance in response.data])

    def test_user_cannot_list_flavors_of_projects_he_has_no_role_in(self):
        inaccessible_project = structure_factories.ProjectFactory()
        factories.CloudProjectMembershipFactory(
            project=inaccessible_project, cloud=self.flavors['inaccessible'].cloud)

        for user_role, flavor in self.forbidden_combinations:
            self._ensure_list_access_forbidden(user_role, flavor)

    def test_user_cannot_list_flavors_not_allowed_for_any_project(self):
        for user_role in ('admin', 'manager', 'no_role'):
            self._ensure_list_access_forbidden(user_role, 'inaccessible')

    # Direct instance access tests
    def test_anonymous_user_cannot_access_flavor(self):
        flavor = factories.FlavorFactory()
        response = self.client.get(self._get_flavor_url(flavor))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_access_flavor_allowed_for_project_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.users['admin'])

        response = self.client.get(self._get_flavor_url(self.flavors['admin']))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_access_flavor_allowed_for_project_he_is_manager_of(self):
        self.client.force_authenticate(user=self.users['manager'])

        response = self.client.get(self._get_flavor_url(self.flavors['manager']))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_access_flavor_allowed_for_project_he_has_no_role_in(self):
        inaccessible_project = structure_factories.ProjectFactory()
        factories.CloudProjectMembershipFactory(
            cloud=self.flavors['inaccessible'].cloud, project=inaccessible_project)

        for user_role, flavor in self.forbidden_combinations:
            self._ensure_direct_access_forbidden(user_role, flavor)

    def test_user_cannot_access_flavor_not_allowed_for_any_project(self):
        for user_role in ('admin', 'manager', 'no_role'):
            self._ensure_direct_access_forbidden(user_role, 'inaccessible')

    # Creation tests
    def test_anonymous_user_cannot_create_flavor(self):
        for old_flavor in self.flavors.values():
            flavor = factories.FlavorFactory(cloud=old_flavor.cloud)
            response = self.client.post(reverse('flavor-list'), self._get_valid_payload(flavor))
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_cannot_create_flavor(self):
        for user in self.users.values():
            self.client.force_authenticate(user=user)

            for old_flavor in self.flavors.values():
                flavor = factories.FlavorFactory(cloud=old_flavor.cloud)
                response = self.client.post(reverse('flavor-list'), self._get_valid_payload(flavor))
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_anonymous_user_cannot_change_flavor(self):
        for flavor in self.flavors.values():
            payload = self._get_valid_payload(flavor)
            response = self.client.put(self._get_flavor_url(flavor), payload)

            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_cannot_change_flavor_allowed_for_project_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.users['admin'])
        flavor = self.flavors['admin']

        payload = self._get_valid_payload(flavor)
        response = self.client.put(self._get_flavor_url(flavor), payload)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_user_cannot_change_flavor_allowed_for_project_he_is_manager_of(self):
        self.client.force_authenticate(user=self.users['manager'])
        flavor = self.flavors['manager']

        payload = self._get_valid_payload(flavor)
        response = self.client.put(self._get_flavor_url(flavor), payload)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # Deletion tests
    def test_anonymous_user_cannot_delete_flavor(self):
        flavor = factories.FlavorFactory()
        response = self.client.delete(self._get_flavor_url(flavor))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_cannot_delete_flavor_allowed_for_project_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.users['admin'])

        response = self.client.delete(self._get_flavor_url(self.flavors['admin']))

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_user_cannot_delete_flavor_allowed_for_project_he_is_manager_of(self):
        self.client.force_authenticate(user=self.users['manager'])

        response = self.client.delete(self._get_flavor_url(self.flavors['manager']))

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # Helper methods
    def _ensure_list_access_forbidden(self, user_role, flavor):
        self.client.force_authenticate(user=self.users[user_role])

        response = self.client.get(reverse('flavor-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        flavor_url = self._get_flavor_url(self.flavors[flavor])
        self.assertNotIn(flavor_url, [instance['url'] for instance in response.data])

    def _ensure_direct_access_forbidden(self, user_role, flavor):
        self.client.force_authenticate(user=self.users[user_role])

        response = self.client.get(self._get_flavor_url(self.flavors[flavor]))
        # 404 is used instead of 403 to hide the fact that the resource exists at all
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def _get_flavor_url(self, flavor):
        return 'http://testserver' + reverse('flavor-detail', kwargs={'uuid': flavor.uuid})

    def _get_valid_payload(self, resource):
        return {
            'name': resource.name,
            'cloud': 'http://testserver' + reverse('cloud-detail', kwargs={'uuid': resource.cloud.uuid}),
            'cores': resource.cores,
            'ram': resource.ram,
            'disk': resource.disk,
        }
