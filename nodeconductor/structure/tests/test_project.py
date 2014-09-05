from __future__ import unicode_literals

import unittest

from django.core.urlresolvers import reverse
from django.test import TestCase
from rest_framework import status
from rest_framework import test

from nodeconductor.structure.tests import factories
from nodeconductor.structure.models import CustomerRole
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


class ProjectApiPermissionTest(test.APISimpleTestCase):
    forbidden_combinations = (
        # User role, Project
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
            'owner': factories.UserFactory(),
            'admin': factories.UserFactory(),
            'manager': factories.UserFactory(),
            'no_role': factories.UserFactory(),
        }

        self.projects = {
            'owner': factories.ProjectFactory(),
            'admin': factories.ProjectFactory(),
            'manager': factories.ProjectFactory(),
            'inaccessible': factories.ProjectFactory(),
        }
        
        self.projects['admin'].add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)
        self.projects['manager'].add_user(self.users['manager'], ProjectRole.MANAGER)

        self.projects['owner'].customer.add_user(self.users['owner'], CustomerRole.OWNER)

    # TODO: Test for customer owners
    # Creation tests
    def test_anonymous_user_cannot_create_project(self):
        for old_project in self.projects.values():
            project = factories.ProjectFactory(customer=old_project.customer)
            response = self.client.post(reverse('project-list'), self._get_valid_payload(project))
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @unittest.skip('Not implemented yet')
    def test_user_cannot_create_project_in_customer_he_doesnt_own(self):
        pass

    @unittest.skip('Not implemented yet')
    def test_user_can_create_project_in_customer_he_owns(self):
        pass

    # List filtration tests
    def test_anonymous_user_cannot_list_projects(self):
        response = self.client.get(reverse('project-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_list_projects_belonging_to_customer_he_owns(self):
        self._ensure_list_access_allowed('owner')

    def test_user_can_list_projects_he_is_administrator_of(self):
        self._ensure_list_access_allowed('admin')

    def test_user_can_list_projects_he_is_manager_of(self):
        self._ensure_list_access_allowed('manager')

    def test_user_cannot_list_projects_he_has_no_role_in(self):
        for user_role, project in self.forbidden_combinations:
            self._ensure_list_access_forbidden(user_role, project)

    # Direct instance access tests
    def test_anonymous_user_cannot_access_project(self):
        project = factories.ProjectFactory()
        response = self.client.get(self._get_project_url(project))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_access_project_belonging_to_customer_he_owns(self):
        self._ensure_direct_access_allowed('owner')

    def test_user_can_access_project_he_is_administrator_of(self):
        self._ensure_direct_access_allowed('admin')

    def test_user_can_access_project_he_is_manager_of(self):
        self._ensure_direct_access_allowed('manager')

    def test_user_cannot_access_project_he_has_no_role_in(self):
        for user_role, project in self.forbidden_combinations:
            self._ensure_direct_access_forbidden(user_role, project)

    # Helper methods
    def _get_project_url(self, project):
        return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})

    def _get_valid_payload(self, resource=None):
        resource = resource or factories.ProjectFactory()
        return {
            'name': resource.name,
            'customer': 'http://testserver' + reverse('customer-detail', kwargs={'uuid': resource.customer.uuid}),
        }

    def _ensure_list_access_allowed(self, user_role):
        self.client.force_authenticate(user=self.users[user_role])

        response = self.client.get(reverse('project-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        project_url = self._get_project_url(self.projects[user_role])
        self.assertIn(project_url, [instance['url'] for instance in response.data])

    def _ensure_list_access_forbidden(self, user_role, project):
        self.client.force_authenticate(user=self.users[user_role])

        response = self.client.get(reverse('project-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        project_url = self._get_project_url(self.projects[project])
        self.assertNotIn(project_url, [resource['url'] for resource in response.data])

    def _ensure_direct_access_allowed(self, user_role):
        self.client.force_authenticate(user=self.users[user_role])
        response = self.client.get(self._get_project_url(self.projects[user_role]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def _ensure_direct_access_forbidden(self, user_role, project):
        self.client.force_authenticate(user=self.users[user_role])

        response = self.client.get(self._get_project_url(self.projects[project]))
        # 404 is used instead of 403 to hide the fact that the resource exists at all
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CustomerOwnerManipulationTest(test.APISimpleTestCase):
    def setUp(self):
        self.user = factories.UserFactory()
        self.client.force_authenticate(user=self.user)

        self.projects = {
            'accessible': factories.ProjectFactory(),
            'inaccessible': factories.ProjectFactory(),
        }
        self.project_urls = {
            'accessible': reverse('project-detail',
                                  kwargs={'uuid': self.projects['accessible'].uuid}),
            'inaccessible': reverse('project-detail',
                                    kwargs={'uuid': self.projects['inaccessible'].uuid}),
        }
        self.customer = factories.CustomerFactory()
        self.customer.add_user(self.user, CustomerRole.OWNER)
        self.foreign_customer = factories.CustomerFactory()
        self.projects['accessible'].add_user(self.user, ProjectRole.MANAGER)

    def test_owner_can_delete_project(self):
        response = self.client.delete(self.project_urls['accessible'])
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_user_can_not_delete_project_that_does_not_belong_to_owned_customer(self):
        response = self.client.delete(self.project_urls['inaccessible'])
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_can_create_project_for_own_customer(self):
        response = self.client.post(reverse('project-list'),
                                    self._get_valid_project_payload(self.projects['accessible']))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_project_for_not_connected_customer(self):
        response = self.client.post(reverse('project-list'),
                                    self._get_valid_project_payload(self.projects['inaccessible']))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_can_change_single_project_field_for_owned_customer_project(self):
        response = self.client.patch(self._get_project_url(self.projects['accessible']),
                                     {'name': 'New project name'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cant_change_single_project_field_for_non_customer(self):
        response = self.client.patch(self._get_project_url(self.projects['inaccessible']),
                                     {'name': 'New project name'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # Helper functions
    def _get_valid_project_payload(self, resource=None):
        resource = resource or factories.ProjectFactory()
        return {
            'name': resource.name,
            'customer': 'http://testserver' + reverse('customer-detail', kwargs={'uuid': resource.customer.uuid}),
        }

    def _get_project_url(self, project):
        return 'http://testserver' + reverse('project-detail',
                                             kwargs={'uuid': project.uuid})


@unittest.skip('Needs to be revised, see NC-82')
class ProjectManipulationTest(test.APISimpleTestCase):
    def setUp(self):
        self.user = factories.UserFactory()
        self.client.force_authenticate(user=self.user)

        self.project = factories.ProjectFactory()
        self.project_url = reverse('project-detail', kwargs={'uuid': self.project.uuid})

    def test_cannot_delete_project(self):
        response = self.client.delete(self.project_url)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_change_project_as_whole(self):
        response = self.client.put(self.project_url, self._get_valid_payload(self.project))

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_change_single_project_field(self):
        data = {
            'name': self.project.name,
        }

        response = self.client.patch(self.project_url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def _get_valid_payload(self, resource=None):
        resource = resource or factories.ProjectFactory()
        return {
            'name': resource.name,
            'customer': 'http://testserver' + reverse('customer-detail', kwargs={'uuid': resource.customer.uuid}),
        }
