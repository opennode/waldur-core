from __future__ import unicode_literals

import unittest

from django.utils import timezone
from freezegun import freeze_time
from rest_framework import status
from rest_framework import test

from nodeconductor.core.models import User
from nodeconductor.structure.models import CustomerRole
from nodeconductor.structure.serializers import PasswordSerializer
from nodeconductor.structure.tests import factories

from . import fixtures


class UserPermissionApiTest(test.APITransactionTestCase):
    def setUp(self):
        self.users = {
            'staff': factories.UserFactory(is_staff=True, agreement_date=timezone.now()),
            'owner': factories.UserFactory(agreement_date=timezone.now()),
            'not_owner': factories.UserFactory(agreement_date=timezone.now()),
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

    def test_staff_can_see_token_in_the_list(self):
        self.client.force_authenticate(self.users['staff'])

        response = self.client.get(factories.UserFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), len(self.users))
        self.assertIsNotNone(response.data[0]['token'])

    def test_staff_can_see_token_and_its_lifetime_of_the_other_user(self):
        self.client.force_authenticate(self.users['staff'])

        response = self.client.get(factories.UserFactory.get_url(self.users['owner']))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['token'])
        self.assertIn('token_lifetime', response.data)

    def test_owner_cannot_see_token_and_its_lifetime_field_in_the_list_of_users(self):
        self.client.force_authenticate(self.users['owner'])

        response = self.client.get(factories.UserFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertIsNot('token', response.data[0])
        self.assertIsNot('token_lifetime', response.data[0])

    def test_owner_can_see_his_token_and_its_lifetime(self):
        self.client.force_authenticate(self.users['owner'])

        response = self.client.get(factories.UserFactory.get_url(self.users['owner']))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['token'])
        self.assertIn('token_lifetime', response.data)

    def test_owner_cannot_see_token_and_its_lifetime_of_the_other_user(self):
        self.client.force_authenticate(self.users['owner'])

        response = self.client.get(factories.UserFactory.get_url(self.users['not_owner']))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('token', response.data)
        self.assertNotIn('token_lifetime', response.data)

    def test_user_can_see_his_token_via_current_filter(self):
        self.client.force_authenticate(self.users['owner'])

        response = self.client.get(factories.UserFactory.get_list_url(), {'current': True})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))
        self.assertIsNotNone('token', response.data[0])
        self.assertIsNotNone('token_lifetime', response.data[0])

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

    # Manipulation tests
    def test_user_can_change_his_account_email(self):
        data = {
            'email': 'example@example.com',
        }

        self._ensure_user_can_change_field(self.users['owner'], 'email', data)

    def test_user_cannot_change_other_account_email(self):
        data = {
            'email': 'example@example.com',
        }

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

    @unittest.skip('Disabling as organization is temporary a read-only field.')
    def test_user_can_change_his_account_organization(self):
        data = {
            'organization': 'test',
            'email': 'example@example.com',
        }

        self._ensure_user_can_change_field(self.users['owner'], 'organization', data)

    def test_user_cannot_change_other_account_organization(self):
        data = {
            'organization': 'test',
            'email': 'example@example.com',
        }

        self._ensure_user_cannot_change_field(self.users['owner'], 'organization', data)

    def test_user_can_change_his_token_lifetime(self):
        data = {
            'email': 'example@example.com',
            'token_lifetime': 100,
        }

        self._ensure_user_can_change_field(self.users['owner'], 'token_lifetime', data)

    def test_user_cannot_change_other_token_lifetime(self):
        data = {
            'email': 'example@example.com',
            'token_lifetime': 100,
        }

        self._ensure_user_cannot_change_field(self.users['owner'], 'token_lifetime', data)

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
        self.assertEqual('Password has been successfully updated.', response.data['detail'])

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
    def test_password_must_be_at_least_7_characters_long(self):
        data = {'password': '123abc'}

        serializer = PasswordSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertDictContainsSubset(
            {'password': ['Ensure this field has at least 7 characters.']}, serializer.errors)

    def test_password_must_contain_digits(self):
        data = {'password': 'abcdefg'}

        serializer = PasswordSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertDictContainsSubset(
            {'password': ['Ensure this field has at least one digit.']}, serializer.errors)

    def test_password_must_contain_letters(self):
        data = {'password': '1234567'}

        serializer = PasswordSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertDictContainsSubset(
            {'password': ['Ensure this field has at least one latin letter.']},
            serializer.errors)

    def test_password_must_not_be_blank(self):
        data = {'password': ''}

        serializer = PasswordSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertDictContainsSubset(
            {'password': ['This field may not be blank.']}, serializer.errors)


class UserFilterTest(test.APITransactionTestCase):

    def test_user_list_can_be_filtered(self):
        supported_filters = [
            'full_name',
            'native_name',
            'organization',
            'email',
            'phone_number',
            'description',
            'job_title',
            'username',
            'civil_number',
            'is_active',
        ]
        user = factories.UserFactory(is_staff=True)
        user_that_should_be_found = factories.UserFactory(
            native_name='',
            organization='',
            email='none@example.com',
            phone_number='',
            description='',
            job_title='',
            username='',
            civil_number='',
            is_active=False,
        )
        self.client.force_authenticate(user)
        url = factories.UserFactory.get_list_url()
        user_url = factories.UserFactory.get_url(user)
        user_that_should_not_be_found_url = factories.UserFactory.get_url(user_that_should_be_found)

        for field in supported_filters:
            response = self.client.get(url, data={field: getattr(user, field)})
            self.assertContains(response, user_url)
            self.assertNotContains(response, user_that_should_not_be_found_url)

    def test_user_list_can_be_filtered_by_fields_with_partial_matching(self):
        supported_filters = [
            'full_name',
            'native_name',
            'email',
            'job_title',
        ]
        user = factories.UserFactory(is_staff=True)
        self.client.force_authenticate(user)
        url = factories.UserFactory.get_list_url()
        user_url = factories.UserFactory.get_url(user)

        for field in supported_filters:
            response = self.client.get(url, data={field: getattr(user, field)[:-1]})
            self.assertContains(response, user_url)


# TODO: temporary flow. Remove once a proper solution is in place.
class UserOrganizationApprovalApiTest(test.APITransactionTestCase):
    def setUp(self):
        self.users = {
            'no_role': factories.UserFactory(organization=""),
            'user_with_request_to_a_customer': factories.UserFactory(),
            'owner': factories.UserFactory(),
            'owner_of_another_customer': factories.UserFactory(),
            'staff': factories.UserFactory(is_staff=True),
        }
        self.customer = factories.CustomerFactory()
        self.customer.add_user(self.users['owner'], CustomerRole.OWNER)

        self.another_customer = factories.CustomerFactory()
        self.another_customer.add_user(self.users['owner_of_another_customer'], CustomerRole.OWNER)

        self.users['user_with_request_to_a_customer'].organization = self.customer.abbreviation
        self.users['user_with_request_to_a_customer'].organization_approved = False
        self.users['user_with_request_to_a_customer'].save()

    # positive
    def test_user_can_claim_organization_membership_if_organization_is_empty(self):
        user = self.users['no_role']
        self.client.force_authenticate(user)
        url = factories.UserFactory.get_url(user, action='claim_organization')
        client_url = factories.UserFactory.get_url(user)

        response = self.client.post(url, data={'organization': self.customer.abbreviation})
        self.assertEquals(response.status_code, status.HTTP_200_OK, response.data)

        #check the status of the claim
        response = self.client.get(client_url)
        self.assertDictContainsSubset(
            {'organization': self.customer.abbreviation,
             'organization_approved': False},
            response.data
        )

    def test_user_can_remove_organization_before_it_is_approved(self):
        user = self.users['user_with_request_to_a_customer']
        self.client.force_authenticate(user)
        url = factories.UserFactory.get_url(user, action='remove_organization')
        client_url = factories.UserFactory.get_url(user)

        response = self.client.post(url)
        self.assertEquals(response.status_code, status.HTTP_200_OK, response.data)

        #check the status of the claim
        response = self.client.get(client_url)
        self.assertDictContainsSubset(
            {'organization': '',
             'organization_approved': False},
            response.data
        )

    def test_user_see_status_of_his_claim_for_organization_membership(self):
        user = self.users['no_role']
        self.client.force_authenticate(user)
        url = factories.UserFactory.get_url(user)

        response = self.client.get(url)
        self.assertTrue(response.status_code, status.HTTP_200_OK)
        self.assertDictContainsSubset(
            {'organization': user.organization,
             'organization_approved': user.organization_approved},
            response.data
        )

    def test_user_who_is_customer_owner_can_see_requests_to_join_his_customer(self):
        self._can_see_status_of_user_claim_for_organization_membership(self.users['owner'])

    def test_user_who_is_customer_owner_can_approve_user_request_to_join_his_customer(self):
        self._can_approve_user_request_to_join_a_customer(self.users['owner'])

    def test_user_who_is_customer_owner_can_reject_user_request_to_join_his_customer(self):
        self._can_reject_user_request_to_join_a_customer(self.users['owner'])

    def test_user_who_is_customer_owner_can_remove_user_from_his_customer_organization(self):
        self._can_remove_user_from_his_customer_organization(self.users['owner'])

    # negative
    def test_user_cannot_claim_organization_membership_if_he_has_approved_one(self):
        user = self.users['user_with_request_to_a_customer']
        user.organization_approved = True
        user.save()

        self.client.force_authenticate(user)
        url = factories.UserFactory.get_url(user, action='claim_organization')

        response = self.client.post(url, data={'organization': self.customer.abbreviation})
        self.assertEquals(response.status_code, status.HTTP_409_CONFLICT, response.data)

    def test_user_cannot_claim_empty_organization_name(self):
        user = self.users['no_role']
        self.client.force_authenticate(user)
        url = factories.UserFactory.get_url(user, action='claim_organization')

        response = self.client.post(url, data={'organization': ''})
        self.assertEquals(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'organization': ['This field may not be blank.']}, response.data)

    def test_user_who_is_not_staff_cannot_claim_organization_membership_of_another_user(self):
        user = self.users['user_with_request_to_a_customer']
        self.client.force_authenticate(user)
        url = factories.UserFactory.get_url(self.users['no_role'], action='claim_organization')

        response = self.client.post(url, data={'organization': self.customer.abbreviation})
        self.assertEquals(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

    def test_user_who_is_not_customer_owner_cannot_approve_user_request_to_join_customer(self):
        user = self.users['no_role']
        self.client.force_authenticate(user)
        url = factories.UserFactory.get_url(self.users['user_with_request_to_a_customer'],
                                            action='approve_organization')

        response = self.client.post(url)
        self.assertEquals(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

    def test_user_who_is_not_customer_owner_cannot_reject_user_request_to_join_customer(self):
        user = self.users['no_role']
        self.client.force_authenticate(user)
        url = factories.UserFactory.get_url(self.users['user_with_request_to_a_customer'],
                                            action='reject_organization')

        response = self.client.post(url)
        self.assertEquals(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

    def test_user_who_is_not_customer_owner_cannot_remove_user_from_customer_organization(self):
        user = self.users['no_role']
        self.client.force_authenticate(user)
        url = factories.UserFactory.get_url(self.users['user_with_request_to_a_customer'],
                                            action='remove_organization')

        response = self.client.post(url)
        self.assertEquals(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

    # staff
    def test_staff_can_see_status_of_user_claim_for_organization_membership(self):
        self._can_see_status_of_user_claim_for_organization_membership(self.users['staff'])

    def test_staff_can_see_requests_to_join_customer(self):
        user = self.users['staff']
        self.client.force_authenticate(user)
        user_url = factories.UserFactory.get_url(self.users['user_with_request_to_a_customer'])
        user_list = factories.UserFactory.get_list_url()
        response = self.client.get(user_list, data={
            'organization': self.customer.abbreviation,
            'organization_approved': False,
        })
        self.assertTrue(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, user_url)
        self.assertTrue(len(response.data) == 1)

    def test_staff_can_approve_user_request_to_join_customer(self):
        self._can_approve_user_request_to_join_a_customer(self.users['staff'])

    def test_staff_can_reject_user_request_to_join_customer(self):
        self._can_reject_user_request_to_join_a_customer(self.users['staff'])

    def test_staff_can_remove_user_from_customer_organization(self):
        self._can_remove_user_from_his_customer_organization(self.users['staff'])

    # helper methods
    def _can_see_status_of_user_claim_for_organization_membership(self, request_user):
        self.client.force_authenticate(request_user)
        user = self.users['no_role']
        url = factories.UserFactory.get_url(user)

        response = self.client.get(url)
        self.assertTrue(response.status_code, status.HTTP_200_OK)
        self.assertDictContainsSubset(
            {'organization': user.organization,
             'organization_approved': user.organization_approved},
            response.data
        )

    def _can_approve_user_request_to_join_a_customer(self, request_user):
        self.client.force_authenticate(request_user)
        url = factories.UserFactory.get_url(self.users['user_with_request_to_a_customer'],
                                            action='approve_organization')
        response = self.client.post(url)

        self.assertEquals(response.status_code, status.HTTP_200_OK)

        # reload user from db
        candidate_user = User.objects.get(username=self.users['user_with_request_to_a_customer'].username)
        self.assertTrue(candidate_user.organization == self.customer.abbreviation)
        self.assertTrue(candidate_user.organization_approved, 'Organization is not approved')

    def _can_reject_user_request_to_join_a_customer(self, request_user):
        self.client.force_authenticate(request_user)
        url = factories.UserFactory.get_url(self.users['user_with_request_to_a_customer'],
                                            action='reject_organization')
        response = self.client.post(url)

        self.assertEquals(response.status_code, status.HTTP_200_OK)

        # reload user from db
        candidate_user = User.objects.get(username=self.users['user_with_request_to_a_customer'].username)
        self.assertTrue(candidate_user.organization == "")
        self.assertFalse(candidate_user.organization_approved, 'Organization is not approved')

    def _can_remove_user_from_his_customer_organization(self, request_user):
        self.client.force_authenticate(request_user)
        url = factories.UserFactory.get_url(self.users['user_with_request_to_a_customer'],
                                            action='remove_organization')
        response = self.client.post(url)

        self.assertEquals(response.status_code, status.HTTP_200_OK)

        # reload user from db
        candidate_user = User.objects.get(username=self.users['user_with_request_to_a_customer'].username)
        self.assertTrue(candidate_user.organization == "")
        self.assertFalse(candidate_user.organization_approved, 'Organization is not approved')


class CustomUsersFilterTest(test.APITransactionTestCase):

    def setUp(self):
        fixture = fixtures.ProjectFixture()
        self.customer1 = fixture.customer
        self.project1 = fixture.project
        self.staff = fixture.staff
        self.owner1 = fixture.owner
        self.manager1 = fixture.manager

        fixture2 = fixtures.ProjectFixture()
        self.customer2 = fixture2.customer
        self.project2 = fixture2.project
        self.owner2 = fixture2.owner
        self.manager2 = fixture2.manager

        self.client.force_authenticate(self.staff)
        self.url = factories.UserFactory.get_list_url()

    def test_filter_user_by_customer(self):
        response = self.client.get(self.url, {'customer_uuid': self.customer1.uuid.hex})
        self.assertEquals(response.status_code, status.HTTP_200_OK)

        actual = [user['uuid'] for user in response.data]
        expected = [self.owner1.uuid.hex, self.manager1.uuid.hex]
        self.assertEquals(actual, expected)

    def test_filter_user_by_project(self):
        response = self.client.get(self.url, {'project_uuid': self.project1.uuid.hex})
        self.assertEquals(response.status_code, status.HTTP_200_OK)

        actual = [user['uuid'] for user in response.data]
        expected = [self.manager1.uuid.hex]
        self.assertEquals(actual, expected)


@freeze_time('2017-01-19 00:00:00')
class UserUpdateTest(test.APITransactionTestCase):
    def setUp(self):
        fixture = fixtures.UserFixture()
        self.user = fixture.user
        self.client.force_authenticate(self.user)
        self.url = factories.UserFactory.get_url(self.user)

        self.invalid_payload = {
            'email': 'updatedmail@example.com',
        }
        self.valid_payload = dict(agree_with_policy=True, **self.invalid_payload)

    def test_if_user_did_not_accept_policy_he_can_not_update_his_profile(self):
        response = self.client.put(self.url, self.invalid_payload)
        self.assertEquals(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEquals(response.data['agree_with_policy'], ['User must agree with the policy.'])

    def test_if_user_already_accepted_policy_he_can_update_his_profile(self):
        self.user.agreement_date = timezone.now()
        self.user.save()

        response = self.client.put(self.url, self.invalid_payload)
        self.assertEquals(response.status_code, status.HTTP_200_OK)

    def test_if_user_accepts_policy_he_can_update_his_profile(self):
        response = self.client.put(self.url, self.valid_payload)
        self.assertEquals(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertEquals(self.user.email, self.valid_payload['email'])

    def test_if_user_accepts_policy_agreement_data_is_updated(self):
        response = self.client.put(self.url, self.valid_payload)
        self.assertEquals(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertAlmostEqual(self.user.agreement_date, timezone.now())

    def test_email_should_be_unique_and_error_should_be_specific_for_field(self):
        email = self.invalid_payload['email']
        factories.UserFactory(email=email)

        response = self.client.put(self.url, self.valid_payload)

        self.assertEquals(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEquals(response.data['email'], ['User with email "%s" already exists.' % email])

    def test_token_lifetime_cannot_be_less_than_60_seconds(self):
        self.valid_payload['token_lifetime'] = 59

        response = self.client.put(self.url, self.valid_payload)
        self.assertEquals(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('token_lifetime', response.data)
