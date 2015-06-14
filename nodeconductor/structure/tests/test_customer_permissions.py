from __future__ import unicode_literals

import collections
import unittest

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework import test
from rest_framework.reverse import reverse

from nodeconductor.structure import serializers
from nodeconductor.structure import views
from nodeconductor.structure.models import CustomerRole, ProjectRole, ProjectGroupRole
from nodeconductor.structure.tests import factories

User = get_user_model()

TestRole = collections.namedtuple('TestRole', ['user', 'customer', 'role'])


class CustomerPermissionViewSetTest(unittest.TestCase):
    def setUp(self):
        self.view_set = views.CustomerPermissionViewSet()

    def test_cannot_modify_permission_in_place(self):
        self.assertNotIn('PUT', self.view_set.allowed_methods)
        self.assertNotIn('PATCH', self.view_set.allowed_methods)

    def test_project_group_permission_serializer_is_used(self):
        self.assertIs(
            serializers.CustomerPermissionSerializer,
            self.view_set.get_serializer_class(),
        )


class CustomerPermissionSerializerTest(unittest.TestCase):
    def setUp(self):
        self.serializer = serializers.CustomerPermissionSerializer()

    def test_payload_has_required_fields(self):
        expected_fields = [
            'url', 'role', 'pk',
            'customer', 'customer_name', 'customer_native_name', 'customer_abbreviation', 'customer_uuid',
            'user', 'user_full_name', 'user_native_name', 'user_username', 'user_uuid', 'user_email'
        ]
        self.assertItemsEqual(expected_fields, self.serializer.fields.keys())


class CustomerPermissionApiPermissionTest(test.APITransactionTestCase):
    all_roles = (
        # user customer role
        TestRole('first', 'first', 'owner'),
        TestRole('second', 'second', 'owner'),
    )

    role_map = {
        'owner': CustomerRole.OWNER,
    }

    def setUp(self):
        self.users = {
            'staff': factories.UserFactory(is_staff=True),
            'first': factories.UserFactory(),
            'first_manager': factories.UserFactory(),
            'first_admin': factories.UserFactory(),
            'second': factories.UserFactory(),
            'no_role': factories.UserFactory(),
        }

        self.customers = {
            'first': factories.CustomerFactory(),
            'second': factories.CustomerFactory(),
        }

        customer = self.customers['first']
        project = factories.ProjectFactory(customer=customer)
        project_group = factories.ProjectGroupFactory(customer=customer)
        project_group.projects.add(project)

        for user, customer, role in self.all_roles:
            self.customers[customer].add_user(self.users[user], self.role_map[role])

        project_group.add_user(self.users['first_manager'], ProjectGroupRole.MANAGER)
        project.add_user(self.users['first_admin'], ProjectRole.ADMINISTRATOR)

    # List filtration tests
    def test_anonymous_user_cannot_list_customer_permissions(self):
        response = self.client.get(reverse('customer_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_cannot_list_roles_of_customer_he_is_not_affiliated(self):
        self.assert_user_access_to_permission_list(user='no_role', customer='first', should_see=False)
        self.assert_user_access_to_permission_list(user='no_role', customer='second', should_see=False)

    def test_customer_owner_can_list_roles_of_his_customer(self):
        self.assert_user_access_to_permission_list(user='first', customer='first', should_see=True)

    def test_project_group_manager_can_list_roles_of_his_customer(self):
        self.assert_user_access_to_permission_list(user='first_manager', customer='first', should_see=True)

    def test_project_admin_can_list_roles_of_his_customer(self):
        self.assert_user_access_to_permission_list(user='first_admin', customer='first', should_see=True)

    def test_staff_can_list_roles_of_any_customer(self):
        self.assert_user_access_to_permission_list(user='staff', customer='first', should_see=True)
        self.assert_user_access_to_permission_list(user='staff', customer='second', should_see=True)

    def test_customer_owner_cannot_list_roles_of_another_customer(self):
        self.assert_user_access_to_permission_list(user='first', customer='second', should_see=False)

    def test_project_group_manager_cannot_list_roles_of_another_customer(self):
        self.assert_user_access_to_permission_list(user='first_manager', customer='second', should_see=False)

    def test_project_admin_cannot_list_roles_of_another_customer(self):
        self.assert_user_access_to_permission_list(user='first_admin', customer='second', should_see=False)

    def assert_user_access_to_permission_list(self, user, customer, should_see):
        self.client.force_authenticate(user=self.users[user])

        response = self.client.get(reverse('customer_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_urls = {
            r: self._get_permission_url(*r)
            for r in self.all_roles
            if r.customer == customer
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
    def test_customer_owner_can_grant_new_role_within_his_customer(self):
        self.assert_user_access_to_permission_granting(
            login_user='first',
            affected_user='no_role',
            affected_customer='first',
            expected_status=status.HTTP_201_CREATED,
        )

    def test_customer_owner_cannot_grant_existing_role_within_his_customer(self):
        self.assert_user_access_to_permission_granting(
            login_user='first',
            affected_user='first',
            affected_customer='first',
            expected_status=status.HTTP_400_BAD_REQUEST,
            expected_payload={
                'non_field_errors': ['The fields customer, user, role must make a unique set.'],
            }
        )

    def test_customer_owner_cannot_grant_role_within_another_customer(self):
        self.assert_user_access_to_permission_granting(
            login_user='first',
            affected_user='no_role',
            affected_customer='second',
            expected_status=status.HTTP_400_BAD_REQUEST,
            expected_payload={
                'customer': ['Invalid hyperlink - Object does not exist.'],
            }
        )

    def test_project_group_manager_cannot_grant_role_within_his_customer(self):
        self.assert_user_access_to_permission_granting(
            login_user='first_manager',
            affected_user='no_role',
            affected_customer='first',
            expected_status=status.HTTP_403_FORBIDDEN,
            expected_payload={
                'detail': 'You do not have permission to perform this action.',
            }
        )

    def test_project_admin_cannot_grant_role_within_his_customer(self):
        self.assert_user_access_to_permission_granting(
            login_user='first_admin',
            affected_user='no_role',
            affected_customer='first',
            expected_status=status.HTTP_403_FORBIDDEN,
            expected_payload={
                'detail': 'You do not have permission to perform this action.',
            }
        )

    def test_staff_can_grant_new_role_within_any_customer(self):
        self.assert_user_access_to_permission_granting(
            login_user='staff',
            affected_user='no_role',
            affected_customer='first',
            expected_status=status.HTTP_201_CREATED,
        )
        self.assert_user_access_to_permission_granting(
            login_user='staff',
            affected_user='no_role',
            affected_customer='second',
            expected_status=status.HTTP_201_CREATED,
        )

    def test_staff_cannot_grant_permission_if_customer_quota_exceeded(self):
        affected_customer = 'first'
        self.customers[affected_customer].set_quota_limit('nc_user_count', 0)

        self.assert_user_access_to_permission_granting(
            login_user='staff',
            affected_user='no_role',
            affected_customer=affected_customer,
            expected_status=status.HTTP_409_CONFLICT,
        )

    def test_staff_cannot_grant_existing_role_within_any_customer(self):
        self.assert_user_access_to_permission_granting(
            login_user='staff',
            affected_user='first',
            affected_customer='first',
            expected_status=status.HTTP_400_BAD_REQUEST,
            expected_payload={
                'non_field_errors': ['The fields customer, user, role must make a unique set.'],
            }
        )
        self.assert_user_access_to_permission_granting(
            login_user='staff',
            affected_user='second',
            affected_customer='second',
            expected_status=status.HTTP_400_BAD_REQUEST,
            expected_payload={
                'non_field_errors': ['The fields customer, user, role must make a unique set.'],
            }
        )

    def assert_user_access_to_permission_granting(self, login_user, affected_user, affected_customer,
                                                  expected_status, expected_payload=None):
        self.client.force_authenticate(user=self.users[login_user])

        data = {
            'customer': factories.CustomerFactory.get_url(self.customers[affected_customer]),
            'user': factories.UserFactory.get_url(self.users[affected_user]),
            'role': 'owner',
        }

        response = self.client.post(reverse('customer_permission-list'), data)
        self.assertEqual(response.status_code, expected_status)
        if expected_payload is not None:
            self.assertDictContainsSubset(expected_payload, response.data)

    # Revocation tests
    def test_customer_owner_can_revoke_role_within_his_customer(self):
        self.assert_user_access_to_permission_revocation(
            login_user='first',
            affected_user='first',
            affected_customer='first',
            expected_status=status.HTTP_204_NO_CONTENT,
        )

    def test_customer_owner_cannot_revoke_role_within_another_customer(self):
        self.assert_user_access_to_permission_revocation(
            login_user='first',
            affected_user='second',
            affected_customer='second',
            expected_status=status.HTTP_404_NOT_FOUND,
        )

    def test_project_group_manager_cannot_revoke_role_within_his_customer(self):
        self.assert_user_access_to_permission_revocation(
            login_user='first_manager',
            affected_user='first',
            affected_customer='first',
            expected_status=status.HTTP_403_FORBIDDEN,
            expected_payload={
                'detail': 'You do not have permission to perform this action.',
            }
        )

    def test_project_admin_cannot_revoke_role_within_his_customer(self):
        self.assert_user_access_to_permission_revocation(
            login_user='first_admin',
            affected_user='first',
            affected_customer='first',
            expected_status=status.HTTP_403_FORBIDDEN,
            expected_payload={
                'detail': 'You do not have permission to perform this action.',
            }
        )

    def test_staff_can_revoke_role_within_any_customer(self):
        self.assert_user_access_to_permission_revocation(
            login_user='staff',
            affected_user='first',
            affected_customer='first',
            expected_status=status.HTTP_204_NO_CONTENT,
        )
        self.assert_user_access_to_permission_revocation(
            login_user='staff',
            affected_user='second',
            affected_customer='second',
            expected_status=status.HTTP_204_NO_CONTENT,
        )

    def assert_user_access_to_permission_revocation(self, login_user, affected_user, affected_customer,
                                                    expected_status, expected_payload=None):
        self.client.force_authenticate(user=self.users[login_user])

        url = self._get_permission_url(affected_user, affected_customer, 'owner')

        response = self.client.delete(url)
        self.assertEqual(response.status_code, expected_status)
        if expected_payload is not None:
            self.assertDictContainsSubset(expected_payload, response.data)

    # Helper methods
    def _get_permission_url(self, user, customer, role):
        permission = User.groups.through.objects.get(
            user=self.users[user],
            group__customerrole__role_type=self.role_map[role],
            group__customerrole__customer=self.customers[customer],
        )
        return 'http://testserver' + reverse('customer_permission-detail', kwargs={'pk': permission.pk})


class CustomerPermissionApiFiltrationTest(test.APISimpleTestCase):
    def setUp(self):
        staff_user = factories.UserFactory(is_staff=True)
        self.client.force_authenticate(user=staff_user)

        self.users = {
            'first': factories.UserFactory(),
            'second': factories.UserFactory(),
        }

        self.customers = {
            'first': factories.CustomerFactory(),
            'second': factories.CustomerFactory(),
        }

        for customer in self.customers:
            self.customers[customer].add_user(self.users['first'], CustomerRole.OWNER)
            self.customers[customer].add_user(self.users['second'], CustomerRole.OWNER)

    def test_staff_user_can_filter_roles_within_customer_by_customer_uuid(self):
        response = self.client.get(reverse('customer_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for customer in self.customers:
            response = self.client.get(reverse('customer_permission-list'),
                                       data={'customer': self.customers[customer].uuid})
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            customer_url = self._get_customer_url(self.customers[customer])

            for permission in response.data:
                self.assertEqual(customer_url, permission['customer'])

    def test_staff_user_can_filter_roles_within_customer_by_username(self):
        response = self.client.get(reverse('customer_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for user in self.users:
            self._ensure_matching_entries_in('username', self.users[user].username)
            self._ensure_non_matching_entries_not_in('username', self.users[user].username)

    def test_staff_user_can_filter_roles_within_customer_by_native_name(self):
        response = self.client.get(reverse('customer_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for user in self.users:
            self._ensure_matching_entries_in('native_name', self.users[user].native_name)
            self._ensure_non_matching_entries_not_in('native_name', self.users[user].native_name)

    def test_staff_user_can_filter_roles_within_customer_by_full_name(self):
        response = self.client.get(reverse('customer_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for user in self.users:
            self._ensure_matching_entries_in('full_name', self.users[user].full_name)
            self._ensure_non_matching_entries_not_in('full_name', self.users[user].full_name)

    def test_staff_user_can_filter_roles_within_customer_by_role_type_name(self):
        response = self.client.get(reverse('customer_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(reverse('customer_permission-list'),
                                   data={'role': 'owner'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for permission in response.data:
            self.assertEqual('owner', permission['role'])

    def test_staff_user_cannot_filter_roles_within_customer_by_role_type_pk(self):
        response = self.client.get(reverse('customer_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(reverse('customer_permission-list'),
                                   data={'role': '1'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_staff_user_can_see_required_fields_in_filtration_response(self):
        response = self.client.get(reverse('customer_permission-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for customer in self.customers:
            response = self.client.get(reverse('customer_permission-list'),
                                       data={'customer': self.customers[customer].uuid})
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            required_fields = ('url', 'user_native_name', 'user_full_name', 'user_username')

            for permission in response.data:
                for field in required_fields:
                    self.assertIn(field, permission)

    # Helper methods
    def _ensure_matching_entries_in(self, field, value):
        response = self.client.get(reverse('customer_permission-list'),
                                   data={field: value})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for permission in response.data:
                self.assertEqual(value, permission['user_' + field])

    def _ensure_non_matching_entries_not_in(self, field, value):
        user = factories.UserFactory()

        customer = factories.CustomerFactory()
        customer.add_user(user, CustomerRole.OWNER)

        response = self.client.get(reverse('customer_permission-list'),
                                   data={field: getattr(user, field)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for permission in response.data:
                self.assertNotEqual(value, permission['user_' + field])

    def _get_customer_url(self, customer):
        return 'http://testserver' + reverse('customer-detail', kwargs={'uuid': customer.uuid})
