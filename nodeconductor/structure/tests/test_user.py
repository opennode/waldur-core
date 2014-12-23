from __future__ import unicode_literals

from django.utils import unittest

from rest_framework import status
from rest_framework import test

from nodeconductor.core.models import User
from nodeconductor.structure.serializers import PasswordSerializer
from nodeconductor.structure.tests import factories


class UserPermissionApiTest(test.APISimpleTestCase):
    def setUp(self):
        self.users = {
            'staff': factories.UserFactory(is_staff=True),
            'owner': factories.UserFactory(),
            'not_owner': factories.UserFactory(),
        }

    # List filtration tests
    def test_anonymous_user_cannot_list_accounts(self):
        response = self.client.get(factories.UserFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authorized_user_can_list_accounts(self):
        self.client.force_authenticate(self.users['owner'])

        response = self.client.get(factories.UserFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_staff_user_can_list_accounts(self):
        self.client.force_authenticate(user=self.users['staff'])

        response = self.client.get(factories.UserFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # Creation tests
    def test_anonymous_user_cannot_create_account(self):
        data = self._get_valid_payload()

        response = self.client.post(factories.UserFactory.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authorized_user_cannot_create_account(self):
        self.client.force_authenticate(self.users['owner'])

        data = self._get_valid_payload()

        response = self.client.post(factories.UserFactory.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_user_can_create_account(self):
        self.client.force_authenticate(self.users['staff'])

        data = self._get_valid_payload()

        response = self.client.post(factories.UserFactory.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        created_user = User.objects.filter(username=data['username']).first()
        self.assertIsNotNone(created_user, 'User should have been created')

    def test_staff_user_cannot_set_civil_number_upon_account_creation(self):
        self.client.force_authenticate(self.users['staff'])

        data = self._get_valid_payload()
        data['civil_number'] = 'foobar'

        response = self.client.post(factories.UserFactory.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        created_user = User.objects.get(username=data['username'])
        self.assertIsNone(created_user.civil_number, "User's civil_number should be unset")

    def test_staff_user_can_create_account_with_null_optional_data(self):
        self.client.force_authenticate(self.users['staff'])

        data = self._get_null_payload()

        response = self.client.post(factories.UserFactory.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # Manipulation tests
    def test_user_can_change_his_account_email(self):
        data = {'email': 'example@example.com'}

        self._ensure_user_can_change_field(self.users['owner'], 'email', data)

    def test_user_cannot_change_other_account_email(self):
        data = {'email': 'example@example.com'}

        self._ensure_user_cannot_change_field(self.users['owner'], 'email', data)

    def test_staff_user_cannot_change_civil_number(self):
        self.client.force_authenticate(self.users['staff'])

        user = factories.UserFactory()

        data = self._get_valid_payload(user)
        data['civil_number'] = 'foobar'

        self.client.put(factories.UserFactory.get_url(user), data)

        reread_user = User.objects.get(username=data['username'])
        self.assertEqual(reread_user.civil_number, user.civil_number,
                         "User's civil_number should be left intact")

    def test_user_can_change_his_account_organization(self):
        data = {'organization': 'test',
                'email': 'example@example.com'}

        self._ensure_user_can_change_field(self.users['owner'], 'organization', data)

    def test_user_cannot_change_other_account_organization(self):
        data = {'organization': 'test',
                'email': 'example@example.com'}

        self._ensure_user_cannot_change_field(self.users['owner'], 'organization', data)

    def test_staff_user_can_change_any_accounts_fields(self):
        self.client.force_authenticate(user=self.users['staff'])
        data = self._get_valid_payload()

        response = self.client.put(factories.UserFactory.get_url(self.users['staff']), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # Password changing tests
    def test_user_can_change_his_account_password(self):
        self.client.force_authenticate(self.users['owner'])

        data = {'password': 'nQvqHzeP123'}

        response = self.client.post(factories.UserFactory.get_password_url(self.users['owner']), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual('Password has been successfully updated', response.data['detail'])

        user = User.objects.get(uuid=self.users['owner'].uuid)
        self.assertTrue(user.check_password(data['password']))

    def test_user_cannot_change_other_account_password(self):
        self.client.force_authenticate(self.users['not_owner'])

        data = {'password': 'nQvqHzeP123'}

        response = self.client.post(factories.UserFactory.get_password_url(self.users['owner']), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        user = User.objects.get(uuid=self.users['owner'].uuid)
        self.assertFalse(user.check_password(data['password']))

    def test_staff_user_can_change_any_accounts_password(self):
        self.client.force_authenticate(self.users['staff'])

        data = {'password': 'nQvqHzeP123'}

        for user in self.users:
            response = self.client.post(factories.UserFactory.get_password_url(self.users[user]), data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            user = User.objects.get(uuid=self.users[user].uuid)
            self.assertTrue(user.check_password(data['password']))

    # Deletion tests
    def user_cannot_delete_his_account(self):
        self._ensure_user_cannot_delete_account(self.users['owner'], self.users['owner'])

    def user_cannot_delete_other_account(self):
        self._ensure_user_cannot_delete_account(self.users['not_owner'], self.users['owner'])

    def test_staff_user_can_delete_any_account(self):
        self.client.force_authenticate(user=self.users['staff'])

        for user in self.users:
            response = self.client.delete(factories.UserFactory.get_url(self.users[user]))
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    # Helper methods
    def _get_valid_payload(self, account=None):
        account = account or factories.UserFactory.build()

        return {
            'username': account.username,
            'email': account.email,
            'full_name': account.full_name,
            'native_name': account.native_name,
            'is_staff': account.is_staff,
            'is_active': account.is_active,
            'is_superuser': account.is_superuser,
        }

    def _get_null_payload(self, account=None):
        account = account or factories.UserFactory.build()

        return {
            'username': account.username,
            'email': account.email,
            'full_name': None,
            'native_name': None,
            'phone_number': None,
            'description': None,
            'is_staff': account.is_staff,
            'is_active': account.is_active,
            'is_superuser': account.is_superuser,
        }

    def _ensure_user_can_change_field(self, user, field_name, data):
        self.client.force_authenticate(user)

        response = self.client.put(factories.UserFactory.get_url(user), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_value = getattr(User.objects.get(uuid=user.uuid), field_name)
        self.assertEqual(new_value, data[field_name])

    def _ensure_user_cannot_change_field(self, user, field_name, data):
        self.client.force_authenticate(user)

        response = self.client.put(factories.UserFactory.get_url(self.users['not_owner']), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        new_value = getattr(User.objects.get(uuid=self.users['not_owner'].uuid), field_name)
        self.assertNotEqual(new_value, data[field_name])

    def _ensure_user_cannot_delete_account(self, user, account):
        self.client.force_authenticate(user=user)

        response = self.client.delete(factories.UserFactory.get_url(account))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PasswordSerializerTest(unittest.TestCase):
    def test_short_password_raises_validation_error(self):
        data = {'password': '123abc'}

        serializer = PasswordSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('Ensure this value has at least 7 characters (it has 6).',
                      serializer.errors['password'])

    def test_password_without_digits_raises_validation_error(self):
        data = {'password': 'abcdefg'}

        serializer = PasswordSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('Password must contain one or more digits',
                      serializer.errors['non_field_errors'])

    def test_password_without_characters_raises_validation_error(self):
        data = {'password': '1234567'}

        serializer = PasswordSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('Password must contain one or more upper- or lower-case characters',
                      serializer.errors['non_field_errors'])

    def test_empty_password_field_raises_validation_error(self):
        data = {'password': ''}

        serializer = PasswordSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('This field is required.',
                      serializer.errors['password'])
