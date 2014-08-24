from __future__ import unicode_literals


import unittest

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.structure.models import CustomerRole
from nodeconductor.structure.models import ProjectRole
from nodeconductor.structure.tests import factories


class ProjectGroupPermissionLifecycleTest(unittest.TestCase):
    """
    This tests how does adding and removal of a Project from
    a ProjectGroup affects permissions of Project's administrators and managers
    with respect to the ProjectGroup.
    """
    # Permission lifecycle test requires at least two tests
    # per role per action.
    #
    # Roles: admin, mgr
    # Action: add, remove, clear
    #
    # Roles * Action * 2 (reversed and non-reversed)

    def setUp(self):
        self.project = factories.ProjectFactory()
        self.project_group = factories.ProjectGroupFactory()

        admin_group = self.project.roles.get(
            role_type=ProjectRole.ADMINISTRATOR).permission_group
        manager_group = self.project.roles.get(
            role_type=ProjectRole.MANAGER).permission_group
        
        self.users = {
            'admin': factories.UserFactory(),
            'manager': factories.UserFactory(),
        }

        admin_group.user_set.add(self.users['admin'])
        manager_group.user_set.add(self.users['manager'])

    # Base test: user has no relation to project group
    def test_user_has_no_access_to_project_group_that_doesnt_contain_any_of_his_projects(self):
        self.assert_user_has_no_access(self.users['admin'], self.project_group)
        self.assert_user_has_no_access(self.users['manager'], self.project_group)

    ## Manager role

    # Addition tests
    def test_manager_gets_readonly_access_to_project_group_when_project_group_is_added_to_managed_project(self):
        self.project.project_groups.add(self.project_group)
        self.assert_user_has_readonly_access(self.users['manager'], self.project_group)

    def test_manager_gets_readonly_access_to_project_group_when_managed_project_is_added_to_project_group(self):
        self.project_group.projects.add(self.project)
        self.assert_user_has_readonly_access(self.users['manager'], self.project_group)

    # Removal tests
    def test_manager_ceases_any_access_from_project_group_when_project_group_is_removed_from_managed_project(self):
        self.project.project_groups.add(self.project_group)
        self.project.project_groups.remove(self.project_group)
        self.assert_user_has_no_access(self.users['manager'], self.project_group)

    def test_manager_ceases_any_access_from_project_group_when_managed_project_is_removed_from_project_group(self):
        self.project_group.projects.add(self.project)
        self.project_group.projects.remove(self.project)
        self.assert_user_has_no_access(self.users['manager'], self.project_group)

    # Clearance tests
    def test_manager_ceases_any_access_from_project_group_when_managed_projects_project_groups_are_cleared(self):
        self.project.project_groups.add(self.project_group)
        self.project.project_groups.clear()
        self.assert_user_has_no_access(self.users['manager'], self.project_group)

    def test_manager_ceases_any_access_from_project_group_when_projects_of_allowed_project_group_are_cleared(self):
        self.project_group.projects.add(self.project)
        self.project_group.projects.clear()
        self.assert_user_has_no_access(self.users['manager'], self.project_group)

    ## Administrator role

    # Addition tests
    def test_administrator_gets_readonly_access_to_project_group_when_project_group_is_added_to_administered_project(self):
        self.project.project_groups.add(self.project_group)
        self.assert_user_has_readonly_access(self.users['admin'], self.project_group)

    def test_administrator_gets_readonly_access_to_project_group_when_administered_project_is_added_to_project_group(self):
        self.project_group.projects.add(self.project)
        self.assert_user_has_readonly_access(self.users['admin'], self.project_group)

    # Removal tests
    def test_administrator_ceases_any_access_from_project_group_when_project_group_is_removed_from_administered_project(self):
        self.project.project_groups.add(self.project_group)
        self.project.project_groups.remove(self.project_group)
        self.assert_user_has_no_access(self.users['admin'], self.project_group)

    def test_administrator_ceases_any_access_from_project_group_when_administered_project_is_removed_from_project_group(self):
        self.project_group.projects.add(self.project)
        self.project_group.projects.remove(self.project)
        self.assert_user_has_no_access(self.users['admin'], self.project_group)

    # Clearance tests
    def test_administrator_ceases_any_access_from_project_group_when_administered_projects_project_groups_are_cleared(self):
        self.project.project_groups.add(self.project_group)
        self.project.project_groups.clear()
        self.assert_user_has_no_access(self.users['admin'], self.project_group)

    def test_administrator_ceases_any_access_from_project_group_when_projects_of_allowed_project_group_are_cleared(self):
        self.project_group.projects.add(self.project)
        self.project_group.projects.clear()
        self.assert_user_has_no_access(self.users['admin'], self.project_group)

    # Helper methods
    def assert_user_has_no_access(self, user, project_group):
        self.assertFalse(user.has_perm('change_projectgroup', obj=project_group))
        self.assertFalse(user.has_perm('delete_projectgroup', obj=project_group))
        self.assertFalse(user.has_perm('view_projectgroup', obj=project_group))

    def assert_user_has_readonly_access(self, user, project_group):
        self.assertFalse(user.has_perm('change_projectgroup', obj=project_group))
        self.assertFalse(user.has_perm('delete_projectgroup', obj=project_group))
        self.assertTrue(user.has_perm('view_projectgroup', obj=project_group))


class ProjectGroupApiPermissionTest(test.APISimpleTestCase):
    def setUp(self):
        self.users = {
            'owner': factories.UserFactory(),
            'admin': factories.UserFactory(),
            'manager': factories.UserFactory(),
            'no_role': factories.UserFactory(),
        }

        self.customer = factories.CustomerFactory()
        self.customer.add_user(self.users['owner'], CustomerRole.OWNER)

        project_groups = factories.ProjectGroupFactory.create_batch(3, customer=self.customer)
        project_groups.append(factories.ProjectGroupFactory())

        self.project_groups = {
            'owner': project_groups[:-1],
            'admin': project_groups[0:2],
            'manager': project_groups[1:3],
            'inaccessible': project_groups[-1:],
        }

        admined_project = factories.ProjectFactory(customer=self.customer)
        admined_project.add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)
        admined_project.project_groups.add(*self.project_groups['admin'])

        managed_project = factories.ProjectFactory(customer=self.customer)
        managed_project.add_user(self.users['manager'], ProjectRole.MANAGER)
        managed_project.project_groups.add(*self.project_groups['manager'])

    # Creation tests
    def test_user_can_create_project_group_belonging_to_customer_he_owns(self):
        self.client.force_authenticate(user=self.users['owner'])

        payload = self._get_valid_payload(factories.ProjectGroupFactory(customer=self.customer))

        response = self.client.post(reverse('projectgroup-list'), payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_user_cannot_create_project_group_belonging_to_customer_he_doesnt_own(self):
        self.client.force_authenticate(user=self.users['owner'])

        payload = self._get_valid_payload()

        response = self.client.post(reverse('projectgroup-list'), payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'customer': ['Invalid hyperlink - object does not exist.']}, response.data)

    # Deletion tests
    def test_user_can_delete_project_group_belonging_to_customer_he_owns(self):
        self.client.force_authenticate(user=self.users['owner'])

        for project_group in self.project_groups['owner']:
            response = self.client.delete(self._get_project_group_url(project_group))
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_user_cannot_delete_project_group_belonging_to_customer_he_doesnt_own(self):
        self.client.force_authenticate(user=self.users['owner'])

        for project_group in self.project_groups['inaccessible']:
            response = self.client.delete(self._get_project_group_url(project_group))
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # TODO: Cannot add other customer's project to own project group
    # List filtration tests
    def test_user_can_list_project_groups_of_customers_he_is_owner_of(self):
        self._ensure_list_access_allowed('owner')

    def test_user_can_list_project_groups_including_projects_he_is_administrator_of(self):
        self._ensure_list_access_allowed('admin')

    def test_user_can_list_project_groups_including_projects_he_is_manager_of(self):
        self._ensure_list_access_allowed('manager')

    def test_user_cannot_list_project_groups_he_has_no_role_in(self):
        self._ensure_list_access_forbidden('owner')
        self._ensure_list_access_forbidden('admin')
        self._ensure_list_access_forbidden('manager')

    # Direct instance access tests
    def test_user_can_access_project_groups_of_customers_he_is_owner_of(self):
        self._ensure_direct_access_allowed('owner')

    def test_user_can_access_project_groups_including_projects_he_is_administrator_of(self):
        self._ensure_direct_access_allowed('admin')

    def test_user_can_access_project_groups_including_projects_he_is_manager_of(self):
        self._ensure_direct_access_allowed('manager')

    def test_user_cannot_access_project_groups_he_has_no_role_in(self):
        self._ensure_direct_access_forbidden('owner')
        self._ensure_direct_access_forbidden('admin')
        self._ensure_direct_access_forbidden('manager')

    # Helper methods
    def _ensure_list_access_allowed(self, user_role):
        self.client.force_authenticate(user=self.users[user_role])

        response = self.client.get(reverse('projectgroup-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        urls = set([instance['url'] for instance in response.data])
        for project_group in self.project_groups[user_role]:
            url = self._get_project_group_url(project_group)

            self.assertIn(url, urls)

    def _ensure_direct_access_allowed(self, user_role):
        self.client.force_authenticate(user=self.users[user_role])
        for project_group in self.project_groups[user_role]:
            url = self._get_project_group_url(project_group)

            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def _ensure_list_access_forbidden(self, user_role):
        self.client.force_authenticate(user=self.users[user_role])

        response = self.client.get(reverse('project-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        urls = set([instance['url'] for instance in response.data])
        for project_group in self.project_groups['inaccessible']:
            url = self._get_project_group_url(project_group)

            self.assertNotIn(url, urls)

    def _ensure_direct_access_forbidden(self, user_role):
        self.client.force_authenticate(user=self.users[user_role])
        for project_group in self.project_groups['inaccessible']:
            response = self.client.get(self._get_project_group_url(project_group))
            # 404 is used instead of 403 to hide the fact that the resource exists at all
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def _get_customer_url(self, customer):
        return 'http://testserver' + reverse('customer-detail', kwargs={'uuid': customer.uuid})

    def _get_project_group_url(self, project_group):
        return 'http://testserver' + reverse('projectgroup-detail', kwargs={'uuid': project_group.uuid})

    def _get_valid_payload(self, resource=None):
        resource = resource or factories.ProjectGroupFactory()

        return {
            'name': resource.name,
            'customer': self._get_customer_url(resource.customer),
        }