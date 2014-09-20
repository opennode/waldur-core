from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.structure.tests import factories
from nodeconductor.structure.models import ProjectRole, CustomerRole


class UserProjectPermissionTest(test.APITransactionTestCase):
    def setUp(self):
        self.users = {
            'owner': factories.UserFactory(),
            'admin': factories.UserFactory(),
            'manager': factories.UserFactory(),
            'no_role': factories.UserFactory(),
        }
        self.client.force_authenticate(user=self.users['owner'])

        customer = factories.CustomerFactory()
        customer.add_user(self.users['owner'], CustomerRole.OWNER)

        self.projects = factories.ProjectFactory.create_batch(3, customer=customer)

        self.projects[0].add_user(self.users['owner'], ProjectRole.MANAGER)
        self.projects[1].add_user(self.users['owner'], ProjectRole.ADMINISTRATOR)

        self.projects[0].add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)

        self.projects[1].add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)
        self.projects[1].add_user(self.users['manager'], ProjectRole.MANAGER)

        self.projects[2].add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)

    def test_user_can_list_roles_of_projects_he_is_manager_of(self):
        response = self.client.get(reverse('project_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertTrue(self._check_if_present(self.projects[0], self.users['owner'], 'manager', response.data),
                        'Owner user doesn\'t have manager privileges')
        self.assertTrue(self._check_if_present(self.projects[0], self.users['admin'], 'admin', response.data),
                        'Admin user doesn\'t have admin privileges')

    def test_user_cannot_list_roles_of_projects_he_has_no_role_in(self):
        response = self.client.get(reverse('project_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertFalse(self._check_if_present(self.projects[2], self.users['no_role'], 'admin', response.data),
                         'Norole user has admin privileges in not connected project')
        self.assertFalse(self._check_if_present(self.projects[2], self.users['no_role'], 'manager', response.data),
                         'Norole user has manager privileges in not connected project')

    def test_user_can_assign_project_roles_of_projects_he_is_manager_of(self):
        user_url = self._get_user_url(self.users['no_role'])

        project_url = self._get_project_url(self.projects[0])

        data = {
            'project': project_url,
            'user': user_url,
            'role': 'manager'
        }

        response = self.client.post(reverse('project_permission-list'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # modification of an existing permission has a different status code
        # XXX This should not fail with 500
        #response = self.client.post(reverse('project_permission-list'), data)
        #self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_cannot_directly_modify_role_of_project_he_is_manager_of(self):
        user_url = self._get_user_url(self.users['no_role'])

        project_url = self._get_project_url(self.projects[0])

        response = self.client.get(reverse('project_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = {
            'project': project_url,
            'user': user_url,
            'role': 'manager'
        }

        for permission in response.data:
            if permission['project'] == project_url:
                response = self.client.put(permission['url'], data)
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_user_can_list_roles_of_projects_he_is_administrator_of(self):
        response = self.client.get(reverse('project_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertTrue(self._check_if_present(self.projects[1], self.users['owner'], 'admin', response.data),
                        'Admin user cannot list his permissions in a project.')
        self.assertTrue(self._check_if_present(self.projects[1], self.users['admin'], 'admin', response.data),
                        'Admin user cannot list admin user permissions in a project.')

    def test_user_cannot_assign_roles_in_projects_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.users['admin'])
        user_url = self._get_user_url(self.users['no_role'])

        project_url = self._get_project_url(self.projects[0])

        data = {
            'project': project_url,
            'user': user_url,
            'role': 'manager'
        }

        response = self.client.post(reverse('project_permission-list'), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_cannot_directly_modify_role_of_project_he_is_administrator_of(self):
        user_url = self._get_user_url(self.users['owner'])

        project_url = self._get_project_url(self.projects[1])

        response = self.client.get(reverse('project_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = {
            'project': project_url,
            'user': user_url,
            'role': 'manager'
        }

        for permission in response.data:
            if permission['project'] == project_url:
                response = self.client.put(permission['url'], data)
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_user_cannot_assign_roles_in_projects_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.users['no_role'])
        user_url = self._get_user_url(self.users['no_role'])

        project_url = self._get_project_url(self.projects[2])

        data = {
            'project': project_url,
            'user': user_url,
            'role': 'manager'
        }

        response = self.client.post(reverse('project_permission-list'), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # Deletion tests
    def test_user_can_delete_role_of_project_he_is_manager_of(self):
        project_url = self._get_project_url(self.projects[0])

        response = self.client.get(reverse('project_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for permission in response.data:
            if permission['project'] == project_url:
                response = self.client.delete(permission['url'])
                self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_user_cannot_delete_role_of_project_he_is_administrator_of(self):
        project_url = self._get_project_url(self.projects[1])

        response = self.client.get(reverse('project_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for permission in response.data:
            if permission['project'] == project_url and permission['role'] == 'admin':
                response = self.client.delete(permission['url'])
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # Helper methods
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
        return {u'role': role,
                u'user': user_url,
                u'project': project_url} in permissions
