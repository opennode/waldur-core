from __future__ import unicode_literals


import unittest

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.structure.models import CustomerRole
from nodeconductor.structure.models import ProjectRole
from nodeconductor.structure.tests import factories


class ProjectGroupApiPermissionTest(test.APISimpleTestCase):
    def setUp(self):
        self.users = {
            'owner': factories.UserFactory(),
            'admin': factories.UserFactory(),
            'manager': factories.UserFactory(),
            'no_role': factories.UserFactory(),
        }

        customer = factories.CustomerFactory()
        customer.add_user(self.users['owner'], CustomerRole.OWNER)

        project_groups = factories.ProjectGroupFactory.create_batch(3, customer=customer)
        project_groups.append(factories.ProjectGroupFactory())

        self.project_groups = {
            'owner': project_groups[:-1],
            'admin': project_groups[0:2],
            'manager': project_groups[1:3],
            'inaccessible': project_groups[-1:],
        }

        admined_project = factories.ProjectFactory(customer=customer)
        admined_project.add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)
        admined_project.project_groups.add(*self.project_groups['admin'])

        managed_project = factories.ProjectFactory(customer=customer)
        managed_project.add_user(self.users['manager'], ProjectRole.MANAGER)
        managed_project.project_groups.add(*self.project_groups['manager'])

        # self.client.force_authenticate(user=self.user)

    # TODO: Creation tests
    # TODO: Cannot add other customer's project to own project group
    # List filtration tests
    def test_user_can_list_project_groups_of_customers_he_is_owner_of(self):
        self._ensure_list_access_allowed('owner')

    @unittest.skip('Not implemented yet')
    def test_user_can_list_project_groups_including_projects_he_is_administrator_of(self):
        self._ensure_list_access_allowed('admin')

    @unittest.skip('Not implemented yet')
    def test_user_can_list_project_groups_including_projects_he_is_manager_of(self):
        self._ensure_list_access_allowed('manager')

    def test_user_cannot_list_project_groups_he_has_no_role_in(self):
        self._ensure_list_access_forbidden('owner')
        self._ensure_list_access_forbidden('admin')
        self._ensure_list_access_forbidden('manager')

    # Direct instance access tests
    def test_user_can_access_project_groups_of_customers_he_is_owner_of(self):
        self._ensure_direct_access_allowed('owner')

    @unittest.skip('Not implemented yet')
    def test_user_can_access_project_groups_including_projects_he_is_administrator_of(self):
        self._ensure_direct_access_allowed('admin')

    @unittest.skip('Not implemented yet')
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

    def _get_project_group_url(self, project_group):
        return 'http://testserver' + reverse('projectgroup-detail', kwargs={'uuid': project_group.uuid})
