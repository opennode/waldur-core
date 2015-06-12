from __future__ import unicode_literals

import collections
import unittest

from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.structure import serializers
from nodeconductor.structure import views
from nodeconductor.structure.models import ProjectRole, CustomerRole, ProjectGroupRole
from nodeconductor.structure.tests import factories

User = get_user_model()

TestRole = collections.namedtuple('TestRole', ['user', 'project', 'role'])


class ProjectPermissionViewSetTest(unittest.TestCase):
    def setUp(self):
        self.view_set = views.ProjectPermissionViewSet()

    def test_cannot_modify_permission_in_place(self):
        self.assertNotIn('PUT', self.view_set.allowed_methods)
        self.assertNotIn('PATCH', self.view_set.allowed_methods)

    def test_project_group_permission_serializer_is_used(self):
        self.assertIs(
            serializers.ProjectPermissionSerializer,
            self.view_set.get_serializer_class(),
        )


class ProjectPermissionSerializerTest(unittest.TestCase):
    def setUp(self):
        self.serializer = serializers.ProjectPermissionSerializer()

    def test_payload_has_required_fields(self):
        expected_fields = [
            'url', 'role', 'project', 'project_name', 'pk', 'project_uuid',
            'user', 'user_full_name', 'user_native_name', 'user_username', 'user_uuid', 'user_email'
        ]
        self.assertItemsEqual(expected_fields, self.serializer.fields.keys())


class ProjectPermissionApiPermissionTest(test.APITransactionTestCase):
    all_roles = (
        #           user      project     role
        TestRole('admin1', 'project11', 'admin'),
        TestRole('admin2', 'project11', 'admin'),
        TestRole('admin3', 'project12', 'admin'),
        TestRole('admin4', 'project13', 'admin'),
        TestRole('admin5', 'project21', 'admin'),
    )

    role_map = {
        'admin': ProjectRole.ADMINISTRATOR,
        'manager': ProjectRole.MANAGER,
    }

    def setUp(self):
        customers = {
            'customer1': factories.CustomerFactory(),
            'customer2': factories.CustomerFactory(),
        }

        project_groups = {
            'group11': factories.ProjectGroupFactory(customer=customers['customer1']),
            'group12': factories.ProjectGroupFactory(customer=customers['customer1']),
            'group21': factories.ProjectGroupFactory(customer=customers['customer2']),
        }

        self.projects = {
            'project11': factories.ProjectFactory(customer=customers['customer1']),
            'project12': factories.ProjectFactory(customer=customers['customer1']),
            'project13': factories.ProjectFactory(customer=customers['customer1']),
            'project21': factories.ProjectFactory(customer=customers['customer2']),
        }

        project_groups['group11'].projects.add(self.projects['project11'], self.projects['project12'])
        project_groups['group12'].projects.add(self.projects['project13'], self.projects['project12'])
        project_groups['group21'].projects.add(self.projects['project21'])

        self.users = {
            'owner1': factories.UserFactory(),
            'owner2': factories.UserFactory(),
            'manager1': factories.UserFactory(),
            'manager2': factories.UserFactory(),
            'manager3': factories.UserFactory(),
            'admin1': factories.UserFactory(),
            'admin2': factories.UserFactory(),
            'admin3': factories.UserFactory(),
            'admin4': factories.UserFactory(),
            'admin5': factories.UserFactory(),
            'no_role': factories.UserFactory(),
            'staff': factories.UserFactory(is_staff=True),
        }

        customers['customer1'].add_user(self.users['owner1'], CustomerRole.OWNER)
        customers['customer2'].add_user(self.users['owner2'], CustomerRole.OWNER)

        project_groups['group11'].add_user(self.users['manager1'], ProjectGroupRole.MANAGER)
        project_groups['group12'].add_user(self.users['manager2'], ProjectGroupRole.MANAGER)
        project_groups['group21'].add_user(self.users['manager3'], ProjectGroupRole.MANAGER)

        for user, project, role in self.all_roles:
            self.projects[project].add_user(self.users[user], ProjectRole.ADMINISTRATOR)

    # List filtration tests
    def test_anonymous_user_cannot_list_project_permissions(self):
        response = self.client.get(reverse('project_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_cannot_list_roles_of_project_he_is_not_affiliated(self):
        for project in self.projects.keys():
            self.assert_user_access_to_permission_list(user='no_role', project=project, should_see=False)

    def test_customer_owner_can_list_roles_of_his_customers_project(self):
        self.assert_user_access_to_permission_list(user='owner1', project='project11', should_see=True)
        self.assert_user_access_to_permission_list(user='owner1', project='project12', should_see=True)
        self.assert_user_access_to_permission_list(user='owner1', project='project13', should_see=True)

    def test_customer_owner_cannot_list_roles_of_another_customers_project(self):
        self.assert_user_access_to_permission_list(user='owner1', project='project21', should_see=False)

    def test_project_group_manager_can_list_roles_of_his_project_groups_project(self):
        self.assert_user_access_to_permission_list(user='manager2', project='project12', should_see=True)
        self.assert_user_access_to_permission_list(user='manager2', project='project13', should_see=True)

    def test_project_group_manager_cannot_list_roles_of_another_project_groups_project(self):
        self.assert_user_access_to_permission_list(user='manager1', project='project13', should_see=False)
        self.assert_user_access_to_permission_list(user='manager1', project='project21', should_see=False)

    def test_project_admin_can_list_roles_of_his_project(self):
        self.assert_user_access_to_permission_list(user='admin1', project='project11', should_see=True)

    def test_project_admin_cannot_list_roles_of_another_project(self):
        self.assert_user_access_to_permission_list(user='admin2', project='project12', should_see=False)
        self.assert_user_access_to_permission_list(user='admin2', project='project13', should_see=False)
        self.assert_user_access_to_permission_list(user='admin2', project='project21', should_see=False)

    def test_staff_can_list_roles_of_any_project(self):
        for project in self.projects.keys():
            self.assert_user_access_to_permission_list(user='staff', project=project, should_see=True)

    def assert_user_access_to_permission_list(self, user, project, should_see):
        self.client.force_authenticate(user=self.users[user])

        response = self.client.get(reverse('project_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_urls = {
            r: self._get_permission_url(*r)
            for r in self.all_roles
            if r.project == project
        }

        actual_urls = set([role['url'] for role in response.data])

        for role, role_url in expected_urls.items():
            if should_see:
                self.assertIn(
                    role_url, actual_urls,
                    '{0} user does not see privilege '
                    'he is supposed to see: {1}'.format(user, role),
                )
            else:
                self.assertNotIn(
                    role_url, actual_urls,
                    '{0} user sees privilege '
                    'he is not supposed to see: {1}'.format(user, role),
                )

    # Granting tests
    def test_customer_owner_can_grant_new_role_within_his_customers_project(self):
        self.assert_user_access_to_permission_granting(
            login_user='owner1',
            affected_user='no_role',
            affected_project='project11',
            expected_status=status.HTTP_201_CREATED,
        )

    def test_customer_owner_cannot_grant_existing_role_within_his_project(self):
        self.assert_user_access_to_permission_granting(
            login_user='owner1',
            affected_user='admin1',
            affected_project='project11',
            expected_status=status.HTTP_400_BAD_REQUEST,
            expected_payload={
                'non_field_errors': ['The fields project, user, role must make a unique set.'],
            }
        )

    def test_customer_owner_cannot_grant_role_within_another_customers_project(self):
        self.assert_user_access_to_permission_granting(
            login_user='owner1',
            affected_user='no_role',
            affected_project='project21',
            expected_status=status.HTTP_400_BAD_REQUEST,
            expected_payload={
                'project': ['Invalid hyperlink - Object does not exist.'],
            }
        )

    def test_project_group_manager_can_grant_new_role_within_his_project_groups_project(self):
        self.assert_user_access_to_permission_granting(
            login_user='manager1',
            affected_user='no_role',
            affected_project='project11',
            expected_status=status.HTTP_201_CREATED,
        )

    def test_project_group_manager_cannot_grant_existing_role_within_his_project_groups_project(self):
        self.assert_user_access_to_permission_granting(
            login_user='manager1',
            affected_user='admin1',
            affected_project='project11',
            expected_status=status.HTTP_400_BAD_REQUEST,
            expected_payload={
                'non_field_errors': ['The fields project, user, role must make a unique set.'],
            }
        )

    def test_project_group_manager_cannot_grant_role_within_another_project_groups_project(self):
        self.assert_user_access_to_permission_granting(
            login_user='manager1',
            affected_user='no_role',
            affected_project='project13',
            expected_status=status.HTTP_400_BAD_REQUEST,
            expected_payload={
                'project': ['Invalid hyperlink - Object does not exist.'],
            }
        )

    def test_project_admin_cannot_grant_new_role_within_his_project(self):
        self.assert_user_access_to_permission_granting(
            login_user='admin1',
            affected_user='no_role',
            affected_project='project11',
            expected_status=status.HTTP_403_FORBIDDEN,
            expected_payload={
                'detail': 'You do not have permission to perform this action.',
            }
        )

    def test_project_admin_cannot_grant_existing_role_within_his_project(self):
        self.assert_user_access_to_permission_granting(
            login_user='admin1',
            affected_user='admin1',
            affected_project='project11',
            expected_status=status.HTTP_400_BAD_REQUEST,
            expected_payload={
                'non_field_errors': ['The fields project, user, role must make a unique set.'],
            }
        )

    def test_project_admin_cannot_grant_role_within_another_project(self):
        self.assert_user_access_to_permission_granting(
            login_user='admin1',
            affected_user='no_role',
            affected_project='project13',
            expected_status=status.HTTP_400_BAD_REQUEST,
            expected_payload={
                'project': ['Invalid hyperlink - Object does not exist.'],
            }
        )

    def test_staff_can_grant_new_role_within_any_project(self):
        for project in self.projects.keys():
            self.assert_user_access_to_permission_granting(
                login_user='staff',
                affected_user='no_role',
                affected_project=project,
                expected_status=status.HTTP_201_CREATED,
            )

    def test_staff_cannot_grant_new_role_if_customer_quota_were_exceeded(self):
        project = 'project11'
        self.projects[project].customer.set_quota_limit('nc_user_count', 0)
        self.assert_user_access_to_permission_granting(
            login_user='staff',
            affected_user='no_role',
            affected_project=project,
            expected_status=status.HTTP_409_CONFLICT,
        )

    def test_staff_cannot_grant_existing_role_within_any_project(self):
        for user, project, _ in self.all_roles:
            self.assert_user_access_to_permission_granting(
                login_user='staff',
                affected_user=user,
                affected_project=project,
                expected_status=status.HTTP_400_BAD_REQUEST,
                expected_payload={
                    'non_field_errors': ['The fields project, user, role must make a unique set.'],
                }
            )

    def assert_user_access_to_permission_granting(self, login_user, affected_user, affected_project,
                                                  expected_status, expected_payload=None):
        self.client.force_authenticate(user=self.users[login_user])

        data = {
            'project': factories.ProjectFactory.get_url(self.projects[affected_project]),
            'user': factories.UserFactory.get_url(self.users[affected_user]),
            'role': 'admin',
        }

        response = self.client.post(reverse('project_permission-list'), data)
        self.assertEqual(response.status_code, expected_status)
        if expected_payload is not None:
            self.assertDictContainsSubset(expected_payload, response.data)

    # Revocation tests
    def test_customer_owner_can_revoke_role_within_his_customers_project(self):
        self.assert_user_access_to_permission_revocation(
            login_user='owner1',
            affected_user='admin1',
            affected_project='project11',
            expected_status=status.HTTP_204_NO_CONTENT,
        )

    def test_customer_owner_cannot_revoke_role_within_another_customers_project(self):
        self.assert_user_access_to_permission_revocation(
            login_user='owner1',
            affected_user='admin5',
            affected_project='project21',
            expected_status=status.HTTP_404_NOT_FOUND,
        )

    def test_project_group_manager_can_revoke_role_within_his_project_groups_project(self):
        self.assert_user_access_to_permission_revocation(
            login_user='manager1',
            affected_user='admin1',
            affected_project='project11',
            expected_status=status.HTTP_204_NO_CONTENT,
        )

    def test_project_group_manager_cannot_revoke_role_within_another_project_groups_project(self):
        self.assert_user_access_to_permission_revocation(
            login_user='manager1',
            affected_user='admin5',
            affected_project='project21',
            expected_status=status.HTTP_404_NOT_FOUND,
        )

    def test_project_admin_cannot_revoke_role_within_his_project(self):
        self.assert_user_access_to_permission_revocation(
            login_user='admin1',
            affected_user='admin2',
            affected_project='project11',
            expected_status=status.HTTP_403_FORBIDDEN,
            expected_payload={
                'detail': 'You do not have permission to perform this action.',
            }
        )

    def test_project_admin_cannot_revoke_role_within_within_another_project(self):
        for user, project, _ in self.all_roles:
            if project == 'project11':
                continue

            self.assert_user_access_to_permission_revocation(
                login_user='admin1',
                affected_user='admin5',
                affected_project='project21',
                expected_status=status.HTTP_404_NOT_FOUND,
            )

    def test_staff_can_revoke_role_within_any_project(self):
        for user, project, _ in self.all_roles:
            self.assert_user_access_to_permission_revocation(
                login_user='staff',
                affected_user=user,
                affected_project=project,
                expected_status=status.HTTP_204_NO_CONTENT,
            )

    def assert_user_access_to_permission_revocation(self, login_user, affected_user, affected_project,
                                                    expected_status, expected_payload=None):
        self.client.force_authenticate(user=self.users[login_user])

        url = self._get_permission_url(affected_user, affected_project, 'admin')

        response = self.client.delete(url)
        self.assertEqual(response.status_code, expected_status)
        if expected_payload is not None:
            self.assertDictContainsSubset(expected_payload, response.data)

    # Helper methods
    def _get_permission_url(self, user, project, role):
        permission = User.groups.through.objects.get(
            user=self.users[user],
            group__projectrole__role_type=self.role_map[role],
            group__projectrole__project=self.projects[project],
        )
        return 'http://testserver' + reverse('project_permission-detail', kwargs={'pk': permission.pk})
