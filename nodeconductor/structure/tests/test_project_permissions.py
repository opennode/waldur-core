from __future__ import unicode_literals

import collections

from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.utils import unittest
from mock import Mock
from rest_framework import status
from rest_framework import test

from nodeconductor.structure.models import ProjectRole, CustomerRole, ProjectGroupRole
from nodeconductor.structure.tests import factories
from nodeconductor.structure.views import ProjectPermissionViewSet

User = get_user_model()

TestRole = collections.namedtuple('TestRole', ['user', 'project', 'role'])


class ProjectPermissionViewSetTest(unittest.TestCase):
    def setUp(self):
        self.view_set = ProjectPermissionViewSet()
        self.request = Mock()
        self.user_group = Mock()

    def test_create_adds_user_role_to_project(self):
        project = self.user_group.group.projectrole.project
        project.add_user.return_value = self.user_group, True

        serializer = Mock()
        serializer.is_valid.return_value = True
        serializer.object = self.user_group

        self.view_set.request = self.request
        self.view_set.can_save = Mock(return_value=True)
        self.view_set.get_serializer = Mock(return_value=serializer)
        self.view_set.create(self.request)

        project.add_user.assert_called_once_with(
            self.user_group.user,
            self.user_group.group.projectrole.role_type,
        )

    def test_destroy_removes_user_role_from_project(self):
        project = self.user_group.group.projectrole.project

        self.view_set.get_object = Mock(return_value=self.user_group)

        self.view_set.destroy(self.request)

        project.remove_user.assert_called_once_with(
            self.user_group.user,
            self.user_group.group.projectrole.role_type,
        )


class UserProjectPermissionTest(test.APITransactionTestCase):
    all_roles = (
        # user        project       role
        TestRole('admin', 'admin', 'admin'),
        TestRole('manager', 'manager', 'manager'),

        TestRole('admin2', 'admin', 'admin'),
        TestRole('admin2', 'manager', 'admin'),
        TestRole('admin2', 'standalone', 'admin'),

        TestRole('manager2', 'admin', 'manager'),
        TestRole('manager2', 'manager', 'manager'),
        TestRole('manager2', 'standalone', 'manager'),
    )

    role_map = {
        'admin': ProjectRole.ADMINISTRATOR,
        'manager': ProjectRole.MANAGER,
    }

    def setUp(self):
        self.users = {
            'admin': factories.UserFactory(),
            'manager': factories.UserFactory(),
            'group_manager': factories.UserFactory(),
            'admin2': factories.UserFactory(),
            'manager2': factories.UserFactory(),
            'no_role': factories.UserFactory(),
        }

        self.customer_owner = factories.UserFactory()
        self.customer = factories.CustomerFactory()
        self.customer.add_user(self.customer_owner, CustomerRole.OWNER)

        self.projects = {
            'admin': factories.ProjectFactory(customer=self.customer),
            'manager': factories.ProjectFactory(),
            'group_manager': factories.ProjectFactory(),
            'standalone': factories.ProjectFactory(),
        }

        for user, project, role in self.all_roles:
            self.projects[project].add_user(self.users[user], self.role_map[role])

        self.project_group = factories.ProjectGroupFactory()
        self.project_group.projects.add(self.projects['group_manager'])
        self.project_group.add_user(self.users['group_manager'], ProjectGroupRole.MANAGER)

    # No role tests
    def test_user_cannot_list_roles_in_projects_he_has_no_role_in(self):
        for login_user in self.users:
            self.client.force_authenticate(user=self.users[login_user])

            response = self.client.get(reverse('project_permission-list'))
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            users_projects = set(r.project for r in self.all_roles if r.user == login_user)
            unseen_roles = (r for r in self.all_roles if r.project not in users_projects)

            for role in unseen_roles:
                role_seen = self._check_if_present(
                    self.projects[role.project],
                    self.users[role.user],
                    role.role,
                    permissions=response.data,
                )

                self.assertFalse(
                    role_seen,
                    '{0} user sees privilege he is not supposed to see: {1}'.format(login_user, role),
                )

    def test_user_cannot_assign_roles_in_projects_he_has_no_role_in(self):
        user_url = self._get_user_url(self.users['no_role'])

        for login_user in self.users:
            self.client.force_authenticate(user=self.users[login_user])

            users_projects = set(r.project for r in self.all_roles if r.user == login_user)
            unseen_projects = set(r.project for r in self.all_roles if r.project not in users_projects)

            for project in unseen_projects:
                project_url = self._get_project_url(self.projects[project])

                data = {
                    'project': project_url,
                    'user': user_url,
                    'role': 'manager'
                }

                response = self.client.post(reverse('project_permission-list'), data)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST,
                                 '{0} user sees privilege he is not supposed to see: {1}. '
                                 'Status code: {2}'.format(login_user, project, response.status_code))
                self.assertDictContainsSubset(
                    {'project': ['Invalid hyperlink - object does not exist.']}, response.data)

    # Manager tests
    def test_user_can_list_roles_of_projects_he_is_manager_of(self):
        self.client.force_authenticate(user=self.users['manager'])

        response = self.client.get(reverse('project_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        manager_roles = (role for role in self.all_roles if role.project == 'manager')

        for role in manager_roles:
            role_seen = self._check_if_present(
                self.projects[role.project],
                self.users[role.user],
                role.role,
                permissions=response.data,
            )

            self.assertTrue(
                role_seen,
                'Manager user does not see a role he is supposed to see: {0}'.format(role),
            )

    def test_user_can_assign_project_roles_in_projects_he_is_manager_of(self):
        self.client.force_authenticate(user=self.users['manager'])

        user_url = self._get_user_url(self.users['no_role'])
        project_url = self._get_project_url(self.projects['manager'])

        data = {
            'project': project_url,
            'user': user_url,
            'role': 'manager'
        }

        response = self.client.post(reverse('project_permission-list'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # modification of an existing permission has a different status code
        response = self.client.post(reverse('project_permission-list'), data)
        self.assertEqual(response.status_code, status.HTTP_304_NOT_MODIFIED)
        self.assertEqual(
            {'detail': 'Permissions were not modified'}, response.data)

        existing_permission_url = self._get_permission_url('no_role', 'manager', 'manager')
        self.assertEqual(response['Location'], existing_permission_url)

    def test_user_can_assign_project_roles_in_projects_he_is_group_manager_of(self):
        self.client.force_authenticate(user=self.users['group_manager'])

        user_url = self._get_user_url(self.users['no_role'])
        project_url = self._get_project_url(self.projects['group_manager'])

        data = {
            'project': project_url,
            'user': user_url,
            'role': 'manager'
        }

        response = self.client.post(reverse('project_permission-list'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # modification of an existing permission has a different status code
        response = self.client.post(reverse('project_permission-list'), data)
        self.assertEqual(response.status_code, status.HTTP_304_NOT_MODIFIED)
        # TODO: Test for Location header pointing to an existing permission

    def test_user_can_assign_project_roles_in_projects_he_is_owner_of(self):
        self.client.force_authenticate(user=self.customer_owner)

        user_url = self._get_user_url(self.users['no_role'])
        project_url = self._get_project_url(self.projects['admin'])

        data = {
            'project': project_url,
            'user': user_url,
            'role': 'manager'
        }

        response = self.client.post(reverse('project_permission-list'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # modification of an existing permission has a different status code
        response = self.client.post(reverse('project_permission-list'), data)
        self.assertEqual(response.status_code, status.HTTP_304_NOT_MODIFIED)
        # TODO: Test for Location header pointing to an existing permission

    def test_user_cannot_directly_modify_role_of_project_he_is_manager_of(self):
        self.client.force_authenticate(user=self.users['manager'])

        managed_roles = (
            role
            for role in self.all_roles
            if role.project == 'manager'
        )

        for role in managed_roles:
            permission_url = self._get_permission_url(*role)

            user_url = self._get_user_url(self.users[role.user])
            project_url = self._get_project_url(self.projects[role.project])

            data = {
                'project': project_url,
                'user': user_url,
                'role': role.role,
            }

            response = self.client.put(permission_url, data)
            self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_user_can_list_roles_of_projects_he_is_owner_of(self):
        self.client.force_authenticate(user=self.customer_owner)

        response = self.client.get(reverse('project_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        manager_roles = (role for role in self.all_roles if role.project == 'admin')

        for role in manager_roles:
            self.assertTrue(
                self._check_if_present(
                    self.projects[role.project],
                    self.users[role.user], role.role, permissions=response.data),
                'Owner user does not see an existing privilege: {0}'.format(role),
            )

    # Administrator tests
    def test_user_can_list_roles_of_projects_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.users['admin'])

        response = self.client.get(reverse('project_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        manager_roles = (role for role in self.all_roles if role.project == 'admin')

        for role in manager_roles:
            self.assertTrue(
                self._check_if_present(
                    self.projects[role.project],
                    self.users[role.user], role.role, permissions=response.data),
                'Manager user does not see an existing privilege: {0}'.format(role),
            )

    def test_user_cannot_assign_roles_in_projects_he_is_administrator_of_but_not_manager_of(self):
        self.client.force_authenticate(user=self.users['admin'])

        user_url = self._get_user_url(self.users['no_role'])
        project_url = self._get_project_url(self.projects['admin'])

        data = {
            'project': project_url,
            'user': user_url,
            'role': 'manager'
        }

        response = self.client.post(reverse('project_permission-list'), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_cannot_directly_modify_role_of_project_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.users['admin'])

        non_managed_roles = (
            role
            for role in self.all_roles
            if role.project == 'admin'
        )

        for role in non_managed_roles:
            permission_url = self._get_permission_url(*role)

            user_url = self._get_user_url(self.users[role.user])
            project_url = self._get_project_url(self.projects[role.project])

            data = {
                'project': project_url,
                'user': user_url,
                'role': role.role,
            }

            response = self.client.put(permission_url, data)
            self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # Deletion tests
    def test_user_can_delete_role_of_project_he_is_manager_of(self):
        self.client.force_authenticate(user=self.users['manager'])
        # We skip deleting manager's permission now
        # otherwise he won't be able to manage roles anymore
        managed_roles = [
            role
            for role in self.all_roles
            if (role.project == 'manager') and (role.user != 'manager')
        ]

        for role in managed_roles:
            permission_url = self._get_permission_url(*role)
            response = self.client.delete(permission_url)
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Now test ability to revoke own manager's role
        permission_url = self._get_permission_url('manager', 'manager', 'manager')
        response = self.client.delete(permission_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_user_cannot_delete_role_of_project_he_is_administrator_of_but_not_manager_of(self):
        self.client.force_authenticate(user=self.users['admin'])

        not_managed_roles = (
            role
            for role in self.all_roles
            if role.project == 'admin'
        )

        for role in not_managed_roles:
            permission_url = self._get_permission_url(*role)
            response = self.client.delete(permission_url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # Helper methods
    def _get_permission_url(self, user, project, role):
        permission = User.groups.through.objects.get(
            user=self.users[user],
            group__projectrole__role_type=self.role_map[role],
            group__projectrole__project=self.projects[project],
        )
        return 'http://testserver' + reverse('project_permission-detail', kwargs={'pk': permission.pk})

    def _get_project_url(self, project):
        return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})

    def _get_user_url(self, user):
        return 'http://testserver' + reverse('user-detail', kwargs={'uuid': user.uuid})

    def _check_if_present(self, project, user, role, permissions):
        project_url = self._get_project_url(project)
        user_url = self._get_user_url(user)
        for permission in permissions:
            if 'url' in permission:
                del permission['url']

        role = {
            'user': user_url,
            'user_full_name': user.full_name,
            'user_native_name': user.native_name,
            'project': project_url,
            'project_name': project.name,
            'role': role,
        }
        return role in permissions
