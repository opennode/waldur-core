from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.structure.tests import factories
from nodeconductor.structure.models import ProjectRole


class UserProjectPermissionTest(test.APISimpleTestCase):
    def setUp(self):
        self.users = factories.UserFactory.create_batch(3)

        self.client.force_authenticate(user=self.users[0])

        self.projects = factories.ProjectFactory.create_batch(3)

        self.projects[0].add_user(self.users[0], ProjectRole.MANAGER)
        self.projects[1].add_user(self.users[0], ProjectRole.ADMINISTRATOR)

        self.projects[0].add_user(self.users[1], ProjectRole.ADMINISTRATOR)

        self.projects[1].add_user(self.users[1], ProjectRole.ADMINISTRATOR)

    def test_user_can_list_roles_of_projects_he_is_manager_of(self):
        response = self.client.get(reverse('user_groups-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertTrue(self._check_if_present(self.projects[0], self.users[0], 'manager', response.data))
        self.assertTrue(self._check_if_present(self.projects[0], self.users[1], 'admin', response.data))
        self.assertFalse(self._check_if_present(self.projects[0], self.users[2], 'admin', response.data))
        self.assertFalse(self._check_if_present(self.projects[0], self.users[2], 'manager', response.data))


    def test_user_can_modify_roles_of_projects_he_is_manager_of(self):
        user_url = self._get_user_url(self.users[1])

        project_url = self._get_project_url(self.projects[0])

        data = {
            'project': project_url,
            'user': user_url,
            'role': 'manager'
        }

        response = self.client.post(reverse('user_groups-list'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # modification of an existing permission has a different status code
        response = self.client.post(reverse('user_groups-list'), data)
        self.assertEqual(response.status_code, status.HTTP_304_NOT_MODIFIED)

    def test_user_can_list_roles_of_projects_he_is_admin_of(self):
        response = self.client.get(reverse('user_groups-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertTrue(self._check_if_present(self.projects[1], self.users[0], 'admin', response.data))
        self.assertTrue(self._check_if_present(self.projects[1], self.users[1], 'admin', response.data))
        self.assertFalse(self._check_if_present(self.projects[1], self.users[0], 'manager', response.data))
        self.assertFalse(self._check_if_present(self.projects[1], self.users[2], 'manager', response.data))
        self.assertFalse(self._check_if_present(self.projects[1], self.users[2], 'admin', response.data))

    def test_user_cannot_modify_roles_of_projects_he_is_admin_of(self):
        user_url = self._get_user_url(self.users[0])

        project_url = self._get_project_url(self.projects[1])

        data = {
            'project': project_url,
            'user': user_url,
            'role': 'manager'
        }

        response = self.client.post(reverse('user_groups-list'), data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

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
