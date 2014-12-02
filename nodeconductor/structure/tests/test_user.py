from __future__ import unicode_literals

from django.core.urlresolvers import reverse

from rest_framework import status
from rest_framework import test

from nodeconductor.core.models import User
from nodeconductor.structure.tests import factories


class UrlResolverMixin(object):
    def _get_user_list_url(self):
        return 'http://testserver' + reverse('user-list')

    def _get_user_url(self, user):
        return 'http://testserver' + reverse('user-detail', kwargs={'uuid': user.uuid})

    def _get_user_password_url(self, user):
        return 'http://testserver' + reverse('user-detail', kwargs={'uuid': user.uuid}) + 'password/'


class UserPermissionApiTest(UrlResolverMixin, test.APISimpleTestCase):
    def setUp(self):
        self.users = {
            'staff': factories.UserFactory(is_staff=True),
            'owner': factories.UserFactory(),
            'not_owner': factories.UserFactory(),
        }

    # List filtration tests
    def test_anonymous_user_cannot_list_accounts(self):
        response = self.client.get(self._get_user_list_url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authorized_user_can_list_accounts(self):
        self.client.force_authenticate(self.users['owner'])

        response = self.client.get(self._get_user_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_staff_user_can_list_accounts(self):
        self.client.force_authenticate(user=self.users['staff'])

        response = self.client.get(self._get_user_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # Creation tests
    def test_anonymous_user_cannot_create_account(self):
        data = self._get_valid_payload()

        response = self.client.post(self._get_user_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authorized_user_cannot_create_account(self):
        self.client.force_authenticate(self.users['owner'])

        data = self._get_valid_payload()

        response = self.client.post(self._get_user_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_user_can_create_account(self):
        self.client.force_authenticate(self.users['staff'])

        data = self._get_valid_payload()

        response = self.client.post(self._get_user_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # Manipulation tests
    def test_user_can_change_his_account_email(self):
        data = {'email': 'example@example.com'}

        self._ensure_user_can_change_field(self.users['owner'], 'email', data)

    def test_user_cannot_change_other_account_email(self):
        data = {'email': 'example@example.com'}

        self._ensure_user_cannot_change_field(self.users['owner'], 'email', data)

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

        response = self.client.put(self._get_user_url(self.users['staff']), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # Password changing tests
    def test_user_can_change_his_account_password(self):
        self.client.force_authenticate(self.users['owner'])

        data = {'password': 'nQvqHzeP123'}

        response = self.client.post(self._get_user_password_url(self.users['owner']), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertFalse(self.users['owner'].check_password(data['password']))

    def test_user_cannot_change_other_account_password(self):
        self.client.force_authenticate(self.users['not_owner'])

        data = {'password': 'nQvqHzeP123'}

        response = self.client.post(self._get_user_password_url(self.users['owner']), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.assertFalse(self.users['not_owner'].check_password(data['password']))

    def test_staff_user_can_change_any_accounts_password(self):
        self.client.force_authenticate(self.users['staff'])

        data = {'password': 'nQvqHzeP123'}

        for user in self.users:
            response = self.client.post(self._get_user_password_url(self.users[user]), data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            self.assertTrue(self.users[user].check_password(data['password']))

    # Helper methods
    def _get_valid_payload(self, account=None):
        account = account or factories.UserFactory.build()

        return {
            'username': account.username,
            'email': account.email,
            'full_name': account.full_name,
            'native_name': account.native_name,
            'civil_number': account.civil_number,
            'is_staff': account.is_staff,
            'is_active': account.is_active,
            'is_superuser': account.is_superuser,
        }

    def _ensure_user_can_change_field(self, user, field_name, data):
        self.client.force_authenticate(user)

        response = self.client.put(self._get_user_url(user), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_value = getattr(User.objects.get(uuid=user.uuid), field_name)
        self.assertEqual(new_value, data[field_name])

    def _ensure_user_cannot_change_field(self, user, field_name, data):
        self.client.force_authenticate(user)

        response = self.client.put(self._get_user_url(self.users['not_owner']), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        new_value = getattr(User.objects.get(uuid=self.users['not_owner'].uuid), field_name)
        self.assertNotEqual(new_value, data[field_name])