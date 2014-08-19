from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from django.test import TestCase
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

        self.projects[1].add_user(self.users[0], ProjectRole.ADMINISTRATOR)

    def test_user_can_list_roles_of_projects_he_is_manager_of(self):
        response = self.client.get(reverse('project-detail', kwargs={'uuid': self.projects[0].uuid}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user_url = self._get_user_url(self.users[0])
        user2_url = self._get_user_url(self.users[1])
        self.assertIn(user_url, [instance['managers'] for instance in response.data])
        self.assertIn(user2_url, [instance['admins'] for instance in response.data])

    def test_user_can_modify_roles_of_projects_he_is_manager_of(self):
        user_url = self._get_user_url(self.users[0])
        user2_url = self._get_user_url(self.users[1])

        project_url = self._get_project_url(self.projects[0])

        data = {
            'managers': [user_url, user2_url],
        }

        response = self.client.patch(self.project_url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_list_roles_of_projects_he_is_admin_of(self):
        response = self.client.get(reverse('project-detail', kwargs={'uuid': self.projects[1].uuid}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user_url = self._get_user_url(self.users[0])
        user2_url = self._get_user_url(self.users[1])
        self.assertIn(user_url, [instance['admins'] for instance in response.data])
        self.assertIn(user2_url, [instance['admins'] for instance in response.data])

    def test_user_cannot_modify_roles_of_projects_he_is_admin_of(self):
        user_url = self._get_user_url(self.users[0])
        user2_url = self._get_user_url(self.users[1])

        project_url = self._get_project_url(self.projects[1])

        data = {
            'managers': [user_url, user2_url],
        }

        response = self.client.patch(self.project_url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


    # Helper methods
    def _get_project_url(self, project):
        return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})

    def _get_user_url(self, user):
        return 'http://testserver' + reverse('users-detail', kwargs={'uuid': user.username})
