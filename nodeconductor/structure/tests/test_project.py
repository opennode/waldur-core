from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from django.test import TestCase
from rest_framework import status
from rest_framework import test

from nodeconductor.structure.tests import factories
from nodeconductor.structure.models import ProjectRole


class ProjectRoleTest(TestCase):
    def setUp(self):
        self.project = factories.ProjectFactory()

    def test_admin_project_role_is_created_upon_project_creation(self):
        self.assertTrue(self.project.roles.filter(role_type=ProjectRole.ADMINISTRATOR).exists(),
                        'Administrator role should have been created')

    def test_manager_project_role_is_created_upon_project_creation(self):
        self.assertTrue(self.project.roles.filter(role_type=ProjectRole.MANAGER).exists(),
                        'Manager role should have been created')


class ProjectPermissionTest(test.APISimpleTestCase):
    def setUp(self):
        self.user = factories.UserFactory.create()
        self.client.force_authenticate(user=self.user)

        self.projects = factories.ProjectFactory.create_batch(3)

        self.projects[0].add_user(self.user, ProjectRole.ADMINISTRATOR)
        self.projects[1].add_user(self.user, ProjectRole.MANAGER)

    # TODO: Test for customer owners

    def test_user_can_list_projects_he_is_administrator_of(self):
        response = self.client.get(reverse('project-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        project_url = self._get_project_url(self.projects[0])
        self.assertIn(project_url, [instance['url'] for instance in response.data])

    def test_user_can_list_projects_he_is_manager_of(self):
        response = self.client.get(reverse('project-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        project_url = self._get_project_url(self.projects[1])
        self.assertIn(project_url, [instance['url'] for instance in response.data])

    def test_user_cannot_list_projects_he_has_no_role_in(self):
        response = self.client.get(reverse('project-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        project_url = self._get_project_url(self.projects[2])
        self.assertNotIn(project_url, [instance['url'] for instance in response.data])

    def test_user_can_access_project_he_is_administrator_of(self):
        response = self.client.get(self._get_project_url(self.projects[0]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_access_project_he_is_manager_of(self):
        response = self.client.get(self._get_project_url(self.projects[1]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_access_project_he_has_no_role_in(self):
        response = self.client.get(self._get_project_url(self.projects[2]))
        # 404 is used instead of 403 to hide the fact that the resource exists at all
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # Helper methods
    def _get_project_url(self, project):
        return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})


class ProjectManipulationTest(test.APISimpleTestCase):
    def setUp(self):
        self.project = factories.ProjectFactory()
        self.project_url = reverse('project-detail', kwargs={'uuid': self.project.uuid})

    def test_cannot_create_project(self):
        # This is temporary constraint until project creation flow
        # is implemented
        data = {
            'name': self.project.name,
        }

        response = self.client.post(reverse('project-list'), data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_delete_project(self):
        response = self.client.delete(self.project_url)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_change_project_as_whole(self):
        data = {
            'name': self.project.name,
        }

        response = self.client.put(self.project_url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_change_single_project_field(self):
        data = {
            'name': self.project.name,
        }

        response = self.client.patch(self.project_url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
