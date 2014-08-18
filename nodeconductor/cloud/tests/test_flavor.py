from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from django.utils import unittest
from rest_framework import status
from rest_framework import test

from nodeconductor.cloud.tests import factories as factories
from nodeconductor.structure.models import ProjectRole
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
            role_type=ProjectRole.ADMINISTRATOR).permission_group
        self.manager_group = self.project.roles.get(
            role_type=ProjectRole.MANAGER).permission_group

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
    def setUp(self):
        self.user = structure_factories.UserFactory.create()
        self.client.force_authenticate(user=self.user)

        admined_project = structure_factories.ProjectFactory()
        managed_project = structure_factories.ProjectFactory()

        admined_project.add_user(self.user, ProjectRole.ADMINISTRATOR)
        managed_project.add_user(self.user, ProjectRole.MANAGER)

        self.admined_flavor = factories.FlavorFactory()
        self.managed_flavor = factories.FlavorFactory()
        self.inaccessible_flavor = factories.FlavorFactory()

        admined_project.clouds.add(self.admined_flavor.cloud)
        managed_project.clouds.add(self.managed_flavor.cloud)

    # List filtration tests
    def test_user_can_list_flavors_of_projects_he_is_administrator_of(self):
        response = self.client.get(reverse('flavor-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        flavor_url = self._get_flavor_url(self.admined_flavor)
        self.assertIn(flavor_url, [instance['url'] for instance in response.data])

    def test_user_can_list_flavors_of_projects_he_is_manager_of(self):
        response = self.client.get(reverse('flavor-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        flavor_url = self._get_flavor_url(self.managed_flavor)
        self.assertIn(flavor_url, [instance['url'] for instance in response.data])

    def test_user_cannot_list_flavors_of_projects_he_has_no_role_in(self):
        inaccessible_project = structure_factories.ProjectFactory()
        inaccessible_project.clouds.add(self.inaccessible_flavor.cloud)

        response = self.client.get(reverse('flavor-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        flavor_url = self._get_flavor_url(self.inaccessible_flavor)
        self.assertNotIn(flavor_url, [instance['url'] for instance in response.data])

    def test_user_cannot_list_flavors_not_allowed_for_any_project(self):
        response = self.client.get(reverse('flavor-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        flavor_url = self._get_flavor_url(self.inaccessible_flavor)
        self.assertNotIn(flavor_url, [instance['url'] for instance in response.data])

    # Direct instance access tests
    def test_user_can_access_flavor_allowed_for_project_he_is_administrator_of(self):
        response = self.client.get(self._get_flavor_url(self.admined_flavor))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_access_flavor_allowed_for_project_he_is_manager_of(self):
        response = self.client.get(self._get_flavor_url(self.managed_flavor))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_access_flavor_allowed_for_project_he_has_no_role_in(self):
        inaccessible_project = structure_factories.ProjectFactory()
        inaccessible_project.clouds.add(self.inaccessible_flavor.cloud)

        response = self.client.get(self._get_flavor_url(self.inaccessible_flavor))
        # 404 is used instead of 403 to hide the fact that the resource exists at all
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_access_flavor_not_allowed_for_any_project(self):
        response = self.client.get(self._get_flavor_url(self.inaccessible_flavor))
        # 404 is used instead of 403 to hide the fact that the resource exists at all
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # Helper methods
    def _get_flavor_url(self, flavor):
        return 'http://testserver' + reverse('flavor-detail', kwargs={'uuid': flavor.uuid})


class FlavorApiManipulationTest(test.APISimpleTestCase):
    def setUp(self):
        self.user = structure_factories.UserFactory.create()
        self.client.force_authenticate(user=self.user)

        self.flavor = factories.FlavorFactory()
        self.flavor_url = 'http://testserver' + reverse('flavor-detail', kwargs={'uuid': self.flavor.uuid})

    def test_cannot_delete_flavor(self):
        response = self.client.delete(self.flavor_url)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_create_flavor(self):
        data = {
            'name': 'test-flavor',
            'cloud': 'http://testserver' + reverse('cloud-detail', kwargs={'uuid': factories.CloudFactory().uuid}),
            'cores': 2,
            'ram': 2.0,
            'disk': 10,
        }

        response = self.client.post(self.flavor_url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_change_flavor_as_whole(self):
        data = {
            'name': self.flavor.name,
            'cloud': 'http://testserver' + reverse('cloud-detail', kwargs={'uuid': self.flavor.cloud.uuid}),
            'cores': self.flavor.cores,
            'ram': self.flavor.ram,
            'disk': self.flavor.disk,
        }

        response = self.client.put(self.flavor_url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_change_single_flavor_field(self):
        data = {
            'name': self.flavor.name,
        }

        response = self.client.patch(self.flavor_url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
