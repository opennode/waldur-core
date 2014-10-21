from __future__ import unicode_literals

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


class ProjectApiPermissionTest(test.APITransactionTestCase):
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
            'multirole': factories.UserFactory(),
        }

        self.projects = {
            'owner': factories.ProjectFactory(),
            'admin': factories.ProjectFactory(),
            'manager': factories.ProjectFactory(),
            'inaccessible': factories.ProjectFactory(),
        }

        self.projects['admin'].add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)
        self.projects['manager'].add_user(self.users['manager'], ProjectRole.MANAGER)

        self.projects['admin'].add_user(self.users['multirole'], ProjectRole.ADMINISTRATOR)
        self.projects['manager'].add_user(self.users['multirole'], ProjectRole.MANAGER)

        self.projects['owner'].customer.add_user(self.users['owner'], CustomerRole.OWNER)

    # TODO: Test for customer owners
    # Creation tests
    def test_anonymous_user_cannot_create_project(self):
        for old_project in self.projects.values():
            project = factories.ProjectFactory(customer=old_project.customer)
            response = self.client.post(reverse('project-list'), self._get_valid_payload(project))
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

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

    def test_user_can_filter_by_projects_where_he_has_manager_role(self):
        self.client.force_authenticate(user=self.users['multirole'])
        response = self.client.get(reverse('project-list') + '?can_manage')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        managed_project_url = self._get_project_url(self.projects['manager'])
        administrated_project_url = self._get_project_url(self.projects['admin'])

        self.assertIn(managed_project_url, [resource['url'] for resource in response.data])
        self.assertNotIn(administrated_project_url, [resource['url'] for resource in response.data])

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


class ProjectManipulationTest(test.APITransactionTestCase):
    def setUp(self):
        self.user = factories.UserFactory()
        self.client.force_authenticate(user=self.user)

        self.customer = factories.CustomerFactory()
        self.customer.add_user(self.user, CustomerRole.OWNER)
        self.foreign_customer = factories.CustomerFactory()

        self.projects = {
            'accessible': factories.ProjectFactory(customer=self.customer),
            'inaccessible': factories.ProjectFactory(customer=self.foreign_customer),
        }
        self.project_urls = {
            'accessible': reverse('project-detail',
                                  kwargs={'uuid': self.projects['accessible'].uuid}),
            'inaccessible': reverse('project-detail',
                                    kwargs={'uuid': self.projects['inaccessible'].uuid}),
        }

    def test_user_can_delete_project_belonging_to_the_customer_he_owns(self):
        response = self.client.delete(self.project_urls['accessible'])
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_user_can_delete_project_if_he_is_staff(self):
        user = factories.UserFactory()
        user.is_staff = True
        user.save()
        self.client.force_authenticate(user=user)
        project = factories.ProjectFactory()
        response = self.client.delete(reverse('project-detail',
                                      kwargs={'uuid': project.uuid}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_user_cannot_delete_project_that_does_not_belong_to_owned_customer(self):
        response = self.client.delete(self.project_urls['inaccessible'])
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_can_create_project_for_own_customer(self):
        response = self.client.post(reverse('project-list'),
                                    self._get_valid_project_payload(self.projects['accessible']))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_user_cannot_create_project_for_customer_he_doesnt_own(self):
        response = self.client.post(reverse('project-list'),
                                    self._get_valid_project_payload(self.projects['inaccessible']))
        # a reference to the invisible customer will be treated as a bad request link
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_can_change_single_project_field_for_project_belonging_to_customer_he_owns(self):
        response = self.client.patch(self._get_project_url(self.projects['accessible']),
                                     {'name': 'New project name'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('New project name', response.data['name'])

    def test_user_cannot_change_single_project_field_for_not_connected_customer(self):
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
