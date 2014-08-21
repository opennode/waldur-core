from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from django.utils import unittest
from rest_framework import status
from rest_framework import test

from nodeconductor.cloud.tests import factories as factories
from nodeconductor.structure.models import Role
from nodeconductor.structure.tests import factories as structure_factories


class FlavorPermissionLifecycleTest(unittest.TestCase):
    # Permission lifecycle test requires at least two tests
    # per role per action.
    #
    # Roles: admin, mgr
    # Action: add, remove, clear
    #
    # Roles * Action * 2 (reversed and non-reversed)

    def setUp(self):
        self.project = structure_factories.ProjectFactory()
        self.flavor = factories.FlavorFactory()
        self.cloud = self.flavor.cloud

        self.admin_group = self.project.roles.get(
            role_type=Role.ADMINISTRATOR).permission_group
        self.manager_group = self.project.roles.get(
            role_type=Role.MANAGER).permission_group

        self.admin = structure_factories.UserFactory()
        self.admin_group.user_set.add(self.admin)

        self.manager = structure_factories.UserFactory()
        self.manager_group.user_set.add(self.manager)

    # Base test: user has no relation to flavor
    def test_user_has_no_access_to_flavor_of_a_cloud_that_is_not_allowed_to_any_of_his_projects(self):
        self.assert_user_has_no_access(self.admin, self.flavor)
        self.assert_user_has_no_access(self.manager, self.flavor)

    ## Manager role

    # Addition tests
    def test_manager_gets_readonly_access_to_flavor_when_flavors_cloud_is_added_to_managed_project(self):
        self.project.clouds.add(self.cloud)
        self.assert_user_has_readonly_access(self.manager, self.flavor)

    def test_manager_gets_readonly_access_to_flavor_when_flavors_managed_project_is_added_to_cloud(self):
        self.cloud.projects.add(self.project)
        self.assert_user_has_readonly_access(self.manager, self.flavor)

    # Removal tests
    def test_manager_ceases_any_access_from_flavor_when_flavors_cloud_is_removed_from_managed_project(self):
        self.project.clouds.add(self.cloud)
        self.project.clouds.remove(self.cloud)
        self.assert_user_has_no_access(self.manager, self.flavor)

    def test_manager_ceases_any_access_from_flavor_when_flavors_managed_project_is_removed_from_cloud(self):
        self.cloud.projects.add(self.project)
        self.cloud.projects.remove(self.project)
        self.assert_user_has_no_access(self.manager, self.flavor)

    # Clearance tests
    def test_manager_ceases_any_access_from_flavor_when_managed_projects_clouds_are_cleared(self):
        self.project.clouds.add(self.cloud)
        self.project.clouds.clear()
        self.assert_user_has_no_access(self.manager, self.flavor)

    def test_manager_ceases_any_access_from_flavor_when_projects_of_cloud_allowed_to_managed_project_are_cleared(self):
        self.cloud.projects.add(self.project)
        self.cloud.projects.clear()
        self.assert_user_has_no_access(self.manager, self.flavor)

    ## Administrator role

    # Addition tests
    def test_administrator_gets_readonly_access_to_flavor_when_flavors_cloud_is_added_to_administered_project(self):
        self.project.clouds.add(self.cloud)
        self.assert_user_has_readonly_access(self.admin, self.flavor)

    def test_administrator_gets_readonly_access_to_flavor_when_flavors_managed_project_is_added_to_cloud(self):
        self.cloud.projects.add(self.project)
        self.assert_user_has_readonly_access(self.admin, self.flavor)

    # Removal tests
    def test_administrator_ceases_any_access_from_flavor_when_flavors_cloud_is_removed_from_administered_project(self):
        self.project.clouds.add(self.cloud)
        self.project.clouds.remove(self.cloud)
        self.assert_user_has_no_access(self.admin, self.flavor)

    def test_administrator_ceases_any_access_from_flavor_when_flavors_administered_project_is_removed_from_cloud(self):
        self.cloud.projects.add(self.project)
        self.cloud.projects.remove(self.project)
        self.assert_user_has_no_access(self.admin, self.flavor)

    # Clearance tests
    def test_administrator_ceases_any_access_from_flavor_when_administered_projects_clouds_are_cleared(self):
        self.project.clouds.add(self.cloud)
        self.project.clouds.clear()
        self.assert_user_has_no_access(self.admin, self.flavor)

    def test_administrator_ceases_any_access_from_flavor_when_projects_of_cloud_allowed_to_administerated_project_are_cleared(self):
        self.cloud.projects.add(self.project)
        self.cloud.projects.clear()
        self.assert_user_has_no_access(self.admin, self.flavor)

    # Helper methods
    def assert_user_has_no_access(self, user, flavor):
        self.assertFalse(user.has_perm('change_flavor', obj=flavor))
        self.assertFalse(user.has_perm('delete_flavor', obj=flavor))
        self.assertFalse(user.has_perm('view_flavor', obj=flavor))

    def assert_user_has_readonly_access(self, user, flavor):
        self.assertFalse(user.has_perm('change_flavor', obj=flavor))
        self.assertFalse(user.has_perm('delete_flavor', obj=flavor))
        self.assertTrue(user.has_perm('view_flavor', obj=flavor))


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

        admined_project.add_user(self.users['admin'], Role.ADMINISTRATOR)
        managed_project.add_user(self.users['manager'], Role.MANAGER)

        admined_project.clouds.add(self.flavors['admin'].cloud)
        managed_project.clouds.add(self.flavors['manager'].cloud)

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
        inaccessible_project.clouds.add(self.flavors['inaccessible'].cloud)

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
        inaccessible_project.clouds.add(self.flavors['inaccessible'].cloud)

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
