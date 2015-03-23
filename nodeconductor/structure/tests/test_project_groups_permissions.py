from __future__ import unicode_literals

import collections

from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.utils import unittest
from rest_framework import test, status

from nodeconductor.structure import serializers
from nodeconductor.structure import views
from nodeconductor.structure.models import CustomerRole, ProjectGroupRole, ProjectRole
from nodeconductor.structure.tests import factories


User = get_user_model()

TestRole = collections.namedtuple('TestRole', ['user', 'project_group', 'role'])


class ProjectGroupPermissionViewSetTest(unittest.TestCase):
    def setUp(self):
        self.view_set = views.ProjectGroupPermissionViewSet()

    def test_cannot_modify_permission_in_place(self):
        self.assertNotIn('PUT', self.view_set.allowed_methods)
        self.assertNotIn('PATCH', self.view_set.allowed_methods)

    def test_project_group_permission_serializer_is_used(self):
        self.assertIs(
            serializers.ProjectGroupPermissionSerializer,
            self.view_set.get_serializer_class(),
        )


class ProjectGroupPermissionSerializerTest(unittest.TestCase):
    def setUp(self):
        self.serializer = serializers.ProjectGroupPermissionSerializer()

    def test_FOO(self):
        expected_fields = [
            'url', 'role', 'project_group', 'project_group_name',
            'user', 'user_full_name', 'user_native_name', 'user_username'
        ]
        self.assertItemsEqual(expected_fields, self.serializer.fields.keys())


class ProjectPermissionApiPermissionTest(test.APITransactionTestCase):
    all_roles = (
        #             user  project_group  role
        TestRole('manager1', 'group11', 'manager'),
        TestRole('manager2', 'group12', 'manager'),
        TestRole('manager3', 'group21', 'manager'),
    )

    role_map = {
        'manager': ProjectGroupRole.MANAGER,
    }

    def setUp(self):
        customers = {
            'customer1': factories.CustomerFactory(),
            'customer2': factories.CustomerFactory(),
        }

        self.project_groups = {
            'group11': factories.ProjectGroupFactory(customer=customers['customer1']),
            'group12': factories.ProjectGroupFactory(customer=customers['customer1']),
            'group21': factories.ProjectGroupFactory(customer=customers['customer2']),
        }

        self.users = {
            'owner1': factories.UserFactory(),
            'owner2': factories.UserFactory(),
            'manager1': factories.UserFactory(),
            'manager2': factories.UserFactory(),
            'manager3': factories.UserFactory(),
            'admin1': factories.UserFactory(),
            'no_role': factories.UserFactory(),
            'staff': factories.UserFactory(is_staff=True),
        }

        customers['customer1'].add_user(self.users['owner1'], CustomerRole.OWNER)
        customers['customer2'].add_user(self.users['owner2'], CustomerRole.OWNER)

        project = factories.ProjectFactory(customer=customers['customer1'])
        project.add_user(self.users['admin1'], ProjectRole.ADMINISTRATOR)
        self.project_groups['group11'].projects.add(project)

        for user, project_group, role in self.all_roles:
            self.project_groups[project_group].add_user(self.users[user], ProjectGroupRole.MANAGER)

    # List filtration tests
    def test_anonymous_user_cannot_list_project_permissions(self):
        response = self.client.get(reverse('projectgroup_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_cannot_list_roles_of_project_he_is_not_affiliated(self):
        for project_group in self.project_groups.keys():
            self.assert_user_access_to_permission_list(user='no_role', project_group=project_group, should_see=False)

    def test_customer_owner_can_list_roles_of_his_customers_project_group(self):
        self.assert_user_access_to_permission_list(user='owner1', project_group='group11', should_see=True)
        self.assert_user_access_to_permission_list(user='owner1', project_group='group12', should_see=True)

    def test_customer_owner_cannot_list_roles_of_another_customers_project_group(self):
        self.assert_user_access_to_permission_list(user='owner1', project_group='group21', should_see=False)

    def test_project_group_manager_can_list_roles_of_his_project_groups(self):
        self.assert_user_access_to_permission_list(user='manager1', project_group='group11', should_see=True)

    def test_project_group_manager_cannot_list_roles_of_another_project_groups(self):
        self.assert_user_access_to_permission_list(user='manager1', project_group='project13', should_see=False)
        self.assert_user_access_to_permission_list(user='manager1', project_group='project21', should_see=False)

    def test_project_admin_can_list_roles_of_his_projects_project_group(self):
        self.assert_user_access_to_permission_list(user='admin1', project_group='group11', should_see=True)

    def test_project_admin_cannot_list_roles_of_another_projects_project_group(self):
        for project_group in self.project_groups.keys():
            if project_group == 'group11':
                continue
            self.assert_user_access_to_permission_list(user='admin1', project_group=project_group, should_see=False)

    def test_staff_can_list_roles_of_any_project_group(self):
        for project_group in self.project_groups.keys():
            self.assert_user_access_to_permission_list(user='staff', project_group=project_group, should_see=True)

    def assert_user_access_to_permission_list(self, user, project_group, should_see):
        self.client.force_authenticate(user=self.users[user])

        response = self.client.get(reverse('projectgroup_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_urls = {
            r: self._get_permission_url(*r)
            for r in self.all_roles
            if r.project_group == project_group
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
    def test_customer_owner_can_grant_new_role_within_his_customers_project_group(self):
        self.assert_user_access_to_permission_granting(
            login_user='owner1',
            affected_user='no_role',
            affected_project_group='group11',
            expected_status=status.HTTP_201_CREATED,
        )

    def test_customer_owner_cannot_grant_existing_role_within_his_project(self):
        self.assert_user_access_to_permission_granting(
            login_user='owner1',
            affected_user='manager1',
            affected_project_group='group11',
            expected_status=status.HTTP_400_BAD_REQUEST,
            expected_payload={
                'non_field_errors': ['The fields project_group, user, role must make a unique set.'],
            }
        )

    def test_customer_owner_cannot_grant_role_within_another_customers_project_group(self):
        self.assert_user_access_to_permission_granting(
            login_user='owner1',
            affected_user='no_role',
            affected_project_group='group21',
            expected_status=status.HTTP_400_BAD_REQUEST,
            expected_payload={
                'project_group': ['Invalid hyperlink - Object does not exist.'],
            }
        )

    def test_project_group_manager_cannot_grant_new_role_within_his_project_group(self):
        self.assert_user_access_to_permission_granting(
            login_user='manager1',
            affected_user='no_role',
            affected_project_group='group11',
            expected_status=status.HTTP_403_FORBIDDEN,
            expected_payload={
                'detail': 'You do not have permission to perform this action.',
            }
        )

    def test_project_group_manager_cannot_grant_existing_role_within_his_project_group(self):
        self.assert_user_access_to_permission_granting(
            login_user='manager1',
            affected_user='manager1',
            affected_project_group='group11',
            expected_status=status.HTTP_400_BAD_REQUEST,
            expected_payload={
                'non_field_errors': ['The fields project_group, user, role must make a unique set.'],
            }
        )

    def test_project_group_manager_cannot_grant_role_within_another_project_group(self):
        self.assert_user_access_to_permission_granting(
            login_user='manager1',
            affected_user='no_role',
            affected_project_group='group12',
            expected_status=status.HTTP_400_BAD_REQUEST,
            expected_payload={
                'project_group': ['Invalid hyperlink - Object does not exist.'],
            }
        )

    def test_project_admin_cannot_grant_new_role_within_his_projects_project_group(self):
        self.assert_user_access_to_permission_granting(
            login_user='admin1',
            affected_user='no_role',
            affected_project_group='group11',
            expected_status=status.HTTP_403_FORBIDDEN,
            expected_payload={
                'detail': 'You do not have permission to perform this action.',
            }
        )

    def test_project_admin_cannot_grant_existing_role_within_his_projects_project_group(self):
        self.assert_user_access_to_permission_granting(
            login_user='admin1',
            affected_user='manager1',
            affected_project_group='group11',
            expected_status=status.HTTP_400_BAD_REQUEST,
            expected_payload={
                'non_field_errors': ['The fields project_group, user, role must make a unique set.'],
            }
        )

    def test_project_admin_cannot_grant_role_within_another_projects_project_group(self):
        self.assert_user_access_to_permission_granting(
            login_user='admin1',
            affected_user='no_role',
            affected_project_group='group12',
            expected_status=status.HTTP_400_BAD_REQUEST,
            expected_payload={
                'project_group': ['Invalid hyperlink - Object does not exist.'],
            }
        )

    def test_staff_can_grant_new_role_within_any_project_group(self):
        for project_group in self.project_groups.keys():
            self.assert_user_access_to_permission_granting(
                login_user='staff',
                affected_user='no_role',
                affected_project_group=project_group,
                expected_status=status.HTTP_201_CREATED,
            )

    def test_staff_cannot_grant_existing_role_within_any_project_group(self):
        for user, project_group, _ in self.all_roles:
            self.assert_user_access_to_permission_granting(
                login_user='staff',
                affected_user=user,
                affected_project_group=project_group,
                expected_status=status.HTTP_400_BAD_REQUEST,
                expected_payload={
                    'non_field_errors': ['The fields project_group, user, role must make a unique set.'],
                }
            )

    def assert_user_access_to_permission_granting(self, login_user, affected_user, affected_project_group,
                                                  expected_status, expected_payload=None):
        self.client.force_authenticate(user=self.users[login_user])

        data = {
            'project_group': factories.ProjectGroupFactory.get_url(self.project_groups[affected_project_group]),
            'user': factories.UserFactory.get_url(self.users[affected_user]),
            'role': 'manager',
        }

        response = self.client.post(reverse('projectgroup_permission-list'), data)
        self.assertEqual(response.status_code, expected_status)
        if expected_payload is not None:
            self.assertDictContainsSubset(expected_payload, response.data)

    # Revocation tests
    def test_customer_owner_can_revoke_role_within_his_customers_project_group(self):
        self.assert_user_access_to_permission_revocation(
            login_user='owner1',
            affected_user='manager1',
            affected_project_group='group11',
            expected_status=status.HTTP_204_NO_CONTENT,
        )

    def test_customer_owner_cannot_revoke_role_within_another_customers_project_group(self):
        self.assert_user_access_to_permission_revocation(
            login_user='owner1',
            affected_user='manager3',
            affected_project_group='group21',
            expected_status=status.HTTP_404_NOT_FOUND,
        )

    def test_project_group_manager_cannot_revoke_role_within_his_project_group(self):
        self.assert_user_access_to_permission_revocation(
            login_user='manager1',
            affected_user='manager1',
            affected_project_group='group11',
            expected_status=status.HTTP_403_FORBIDDEN,
            expected_payload={
                'detail': 'You do not have permission to perform this action.',
            }
        )

    def test_project_group_manager_cannot_revoke_role_within_another_project_group(self):
        self.assert_user_access_to_permission_revocation(
            login_user='manager1',
            affected_user='manager2',
            affected_project_group='group12',
            expected_status=status.HTTP_404_NOT_FOUND,
        )

    def test_project_admin_cannot_revoke_role_within_his_projects_project_group(self):
        self.assert_user_access_to_permission_revocation(
            login_user='admin1',
            affected_user='manager1',
            affected_project_group='group11',
            expected_status=status.HTTP_403_FORBIDDEN,
            expected_payload={
                'detail': 'You do not have permission to perform this action.',
            }
        )

    def test_project_admin_cannot_revoke_role_within_another_projects_project_group(self):
        self.assert_user_access_to_permission_revocation(
            login_user='admin1',
            affected_user='manager2',
            affected_project_group='group12',
            expected_status=status.HTTP_404_NOT_FOUND,
        )

    def test_staff_can_revoke_role_within_any_project_group(self):
        for user, project_group, _ in self.all_roles:
            self.assert_user_access_to_permission_revocation(
                login_user='staff',
                affected_user=user,
                affected_project_group=project_group,
                expected_status=status.HTTP_204_NO_CONTENT,
            )

    def assert_user_access_to_permission_revocation(self, login_user, affected_user, affected_project_group,
                                                    expected_status, expected_payload=None):
        self.client.force_authenticate(user=self.users[login_user])

        url = self._get_permission_url(affected_user, affected_project_group, 'manager')

        response = self.client.delete(url)
        self.assertEqual(response.status_code, expected_status)
        if expected_payload is not None:
            self.assertDictContainsSubset(expected_payload, response.data)

    # Helper methods
    def _get_permission_url(self, user, project_group, role):
        permission = User.groups.through.objects.get(
            user=self.users[user],
            group__projectgrouprole__role_type=self.role_map[role],
            group__projectgrouprole__project_group=self.project_groups[project_group],
        )
        return 'http://testserver' + reverse('projectgroup_permission-detail', kwargs={'pk': permission.pk})
