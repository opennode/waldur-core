# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from unittest import TestCase

from ddt import data, ddt
from django.core.urlresolvers import reverse
from django.test import TransactionTestCase
from mock_django import mock_signal_receiver
from permission.utils.logics import add_permission_logic, remove_permission_logic
from rest_framework import status, test

from nodeconductor.structure import signals
from nodeconductor.structure.models import Customer, CustomerRole, ProjectRole
from nodeconductor.structure.perms import OWNER_CAN_MANAGE_CUSTOMER_LOGICS
from nodeconductor.structure.tests import factories, fixtures


class UrlResolverMixin(object):
    def _get_customer_url(self, customer):
        return 'http://testserver' + reverse('customer-detail', kwargs={'uuid': customer.uuid})

    def _get_project_url(self, project):
        return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})

    def _get_user_url(self, user):
        return 'http://testserver' + reverse('user-detail', kwargs={'uuid': user.uuid})


class CustomerTest(TransactionTestCase):
    def setUp(self):
        self.customer = factories.CustomerFactory()
        self.user = factories.UserFactory()

    def test_add_user_returns_created_if_grant_didnt_exist_before(self):
        _, created = self.customer.add_user(self.user, CustomerRole.OWNER)

        self.assertTrue(created, 'Customer permission should have been reported as created')

    def test_add_user_returns_not_created_if_grant_existed_before(self):
        self.customer.add_user(self.user, CustomerRole.OWNER)
        _, created = self.customer.add_user(self.user, CustomerRole.OWNER)

        self.assertFalse(created, 'Customer permission should have been reported as not created')

    def test_add_user_returns_membership(self):
        membership, _ = self.customer.add_user(self.user, CustomerRole.OWNER)

        self.assertEqual(membership.user, self.user)
        self.assertEqual(membership.customer, self.customer)

    def test_add_user_returns_same_membership_for_consequent_calls_with_same_arguments(self):
        membership1, _ = self.customer.add_user(self.user, CustomerRole.OWNER)
        membership2, _ = self.customer.add_user(self.user, CustomerRole.OWNER)

        self.assertEqual(membership1, membership2)

    def test_add_user_emits_structure_role_granted_if_grant_didnt_exist_before(self):
        with mock_signal_receiver(signals.structure_role_granted) as receiver:
            self.customer.add_user(self.user, CustomerRole.OWNER)

        receiver.assert_called_once_with(
            structure=self.customer,
            user=self.user,
            role=CustomerRole.OWNER,

            sender=Customer,
            signal=signals.structure_role_granted,
        )

    def test_add_user_doesnt_emit_structure_role_granted_if_grant_existed_before(self):
        self.customer.add_user(self.user, CustomerRole.OWNER)

        with mock_signal_receiver(signals.structure_role_granted) as receiver:
            self.customer.add_user(self.user, CustomerRole.OWNER)

        self.assertFalse(receiver.called, 'structure_role_granted should not be emitted')

    def test_remove_user_emits_structure_role_revoked_for_each_role_user_had_in_customer(self):
        self.customer.add_user(self.user, CustomerRole.OWNER)

        with mock_signal_receiver(signals.structure_role_revoked) as receiver:
            self.customer.remove_user(self.user)

        receiver.assert_called_once_with(
            structure=self.customer,
            user=self.user,
            role=CustomerRole.OWNER,

            sender=Customer,
            signal=signals.structure_role_revoked,
        )

    def test_remove_user_emits_structure_role_revoked_if_grant_existed_before(self):
        self.customer.add_user(self.user, CustomerRole.OWNER)

        with mock_signal_receiver(signals.structure_role_revoked) as receiver:
            self.customer.remove_user(self.user, CustomerRole.OWNER)

        receiver.assert_called_once_with(
            structure=self.customer,
            user=self.user,
            role=CustomerRole.OWNER,

            sender=Customer,
            signal=signals.structure_role_revoked,
        )

    def test_remove_user_doesnt_emit_structure_role_revoked_if_grant_didnt_exist_before(self):
        with mock_signal_receiver(signals.structure_role_revoked) as receiver:
            self.customer.remove_user(self.user, CustomerRole.OWNER)

        self.assertFalse(receiver.called, 'structure_role_remove should not be emitted')


class CustomerRoleTest(TransactionTestCase):
    def setUp(self):
        self.customer = factories.CustomerFactory()

    def test_get_owners_returns_empty_list(self):
        self.assertEqual(0, self.customer.get_owners().count())


class CustomerApiPermissionTest(UrlResolverMixin, test.APITransactionTestCase):
    def setUp(self):
        self.users = {
            'staff': factories.UserFactory(is_staff=True),
            'owner': factories.UserFactory(),
            'not_owner': factories.UserFactory(),
            'admin': factories.UserFactory(),
            'admin_other': factories.UserFactory(),
            'manager': factories.UserFactory(),
        }

        self.customers = {
            'owned': factories.CustomerFactory.create_batch(2),
            'inaccessible': factories.CustomerFactory.create_batch(2),
            'admin': factories.CustomerFactory(),
            'manager': factories.CustomerFactory(),
        }

        for customer in self.customers['owned']:
            customer.add_user(self.users['owner'], CustomerRole.OWNER)

        self.projects = {
            'admin': factories.ProjectFactory(customer=self.customers['admin']),
            'manager': factories.ProjectFactory(customer=self.customers['manager']),
        }

        self.projects['admin'].add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)
        self.projects['manager'].add_user(self.users['manager'], ProjectRole.MANAGER)

    # List filtration tests
    def test_user_can_list_customers_he_is_owner_of(self):
        self.client.force_authenticate(user=self.users['owner'])

        self._check_user_list_access_customers(self.customers['owned'], 'assertIn')

    def test_user_cannot_list_customers_he_is_not_owner_of(self):
        self.client.force_authenticate(user=self.users['not_owner'])

        self._check_user_list_access_customers(self.customers['inaccessible'], 'assertNotIn')

    def test_user_can_list_customers_if_he_is_staff(self):
        self.client.force_authenticate(user=self.users['staff'])

        self._check_user_list_access_customers(self.customers['owned'], 'assertIn')

        self._check_user_list_access_customers(self.customers['inaccessible'], 'assertIn')

    def test_user_can_list_customer_if_he_is_admin_in_a_project_owned_by_a_customer(self):
        self.client.force_authenticate(user=self.users['admin'])
        self._check_customer_in_list(self.customers['admin'])

    def test_user_can_list_customer_if_he_is_manager_in_a_project_owned_by_a_customer(self):
        self.client.force_authenticate(user=self.users['manager'])
        self._check_customer_in_list(self.customers['manager'])

    def test_user_cannot_list_customer_if_he_is_admin_in_a_project_not_owned_by_a_customer(self):
        self.client.force_authenticate(user=self.users['admin'])
        self._check_customer_in_list(self.customers['manager'], False)

    def test_user_cannot_list_customer_if_he_is_manager_in_a_project_not_owned_by_a_customer(self):
        self.client.force_authenticate(user=self.users['manager'])
        self._check_customer_in_list(self.customers['admin'], False)

    # Nested objects filtration tests
    def test_user_can_see_project_he_has_a_role_in_within_customer(self):
        for user_role in ('admin', 'manager'):
            self.client.force_authenticate(user=self.users[user_role])

            customer = self.customers[user_role]

            seen_project = self.projects[user_role]

            response = self.client.get(self._get_customer_url(customer))
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            project_urls = set([project['url'] for project in response.data['projects']])
            self.assertIn(
                self._get_project_url(seen_project), project_urls,
                'User should see project',
            )

    def test_user_cannot_see_project_he_has_no_role_in_within_customer(self):
        for user_role in ('admin', 'manager'):
            self.client.force_authenticate(user=self.users[user_role])

            customer = self.customers[user_role]

            non_seen_project = factories.ProjectFactory(customer=customer)

            response = self.client.get(self._get_customer_url(customer))
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            project_urls = set([project['url'] for project in response.data['projects']])
            self.assertNotIn(
                self._get_project_url(non_seen_project), project_urls,
                'User should not see project',
            )

    # Direct instance access tests
    def test_user_can_access_customers_he_is_owner_of(self):
        self.client.force_authenticate(user=self.users['owner'])

        self._check_user_direct_access_customer(self.customers['owned'], status.HTTP_200_OK)

    def test_user_can_see_its_owner_membership_in_a_service_he_is_owner_of(self):
        self.client.force_authenticate(user=self.users['owner'])
        for customer in self.customers['owned']:
            response = self.client.get(self._get_customer_url(customer))
            owners = set(c['url'] for c in response.data['owners'])
            user_url = self._get_user_url(self.users['owner'])
            self.assertItemsEqual([user_url], owners)

    def test_user_cannot_access_customers_he_is_not_owner_of(self):
        self.client.force_authenticate(user=self.users['not_owner'])
        # 404 is used instead of 403 to hide the fact that the resource exists at all
        self._check_user_direct_access_customer(self.customers['inaccessible'], status.HTTP_404_NOT_FOUND)

    def test_user_can_access_all_customers_if_he_is_staff(self):
        self.client.force_authenticate(user=self.users['staff'])

        self._check_user_direct_access_customer(self.customers['owned'], status.HTTP_200_OK)

        self._check_user_direct_access_customer(self.customers['inaccessible'], status.HTTP_200_OK)

    # Helper methods
    def _check_user_list_access_customers(self, customers, test_function):
        response = self.client.get(reverse('customer-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        urls = set([instance['url'] for instance in response.data])
        for customer in customers:
            url = self._get_customer_url(customer)

            getattr(self, test_function)(url, urls)

    def _check_customer_in_list(self, customer, positive=True):
        response = self.client.get(reverse('customer-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        urls = set([instance['url'] for instance in response.data])
        customer_url = self._get_customer_url(customer)
        if positive:
            self.assertIn(customer_url, urls)
        else:
            self.assertNotIn(customer_url, urls)

    def _check_user_direct_access_customer(self, customers, status_code):
        for customer in customers:
            response = self.client.get(self._get_customer_url(customer))

            self.assertEqual(response.status_code, status_code)


class CustomerApiManipulationTest(UrlResolverMixin, test.APISimpleTestCase):
    def setUp(self):
        self.users = {
            'staff': factories.UserFactory(is_staff=True),
            'owner': factories.UserFactory(),
            'not_owner': factories.UserFactory(),
        }

        self.customers = {
            'owner': factories.CustomerFactory(),
            'inaccessible': factories.CustomerFactory(),
        }

        self.customers['owner'].add_user(self.users['owner'], CustomerRole.OWNER)

    # Deletion tests
    def test_user_cannot_delete_customer_he_is_not_owner_of(self):
        self.client.force_authenticate(user=self.users['not_owner'])

        response = self.client.delete(self._get_customer_url(self.customers['inaccessible']))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_delete_customer_he_is_owner_of(self):
        self.client.force_authenticate(user=self.users['owner'])

        response = self.client.delete(self._get_customer_url(self.customers['owner']))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_cannot_delete_customer_with_associated_projects_if_he_is_staff(self):
        self.client.force_authenticate(user=self.users['staff'])

        for customer in self.customers.values():
            factories.ProjectFactory(customer=customer)

            response = self.client.delete(self._get_customer_url(customer))

            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
            self.assertDictContainsSubset({'detail': 'Cannot delete customer with existing projects'},
                                          response.data)

    # Creation tests
    def test_user_can_not_create_customer_if_he_is_not_staff(self):
        self.client.force_authenticate(user=self.users['not_owner'])

        response = self.client.post(reverse('customer-list'), self._get_valid_payload())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_can_create_customer_if_he_is_not_staff_if_settings_are_tweaked(self):
        add_permission_logic(Customer, OWNER_CAN_MANAGE_CUSTOMER_LOGICS)
        self.client.force_authenticate(user=self.users['not_owner'])

        response = self.client.post(reverse('customer-list'), self._get_valid_payload())

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # User became owner of created customer
        self.assertEqual(response.data['owners'][0]['uuid'], self.users['not_owner'].uuid.hex)
        remove_permission_logic(Customer, OWNER_CAN_MANAGE_CUSTOMER_LOGICS)

    def test_user_can_create_customer_if_he_is_staff(self):
        self.client.force_authenticate(user=self.users['staff'])

        response = self.client.post(reverse('customer-list'), self._get_valid_payload())

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # Mutation tests
    def test_user_cannot_change_customer_as_whole_he_is_not_owner_of(self):
        self.client.force_authenticate(user=self.users['not_owner'])

        response = self.client.put(self._get_customer_url(self.customers['inaccessible']),
                                   self._get_valid_payload())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_change_customer_he_is_owner_of(self):
        self.client.force_authenticate(user=self.users['owner'])

        response = self.client.put(self._get_customer_url(self.customers['owner']),
                                   self._get_valid_payload())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_can_change_customer_as_whole_if_he_is_staff(self):
        self.client.force_authenticate(user=self.users['staff'])

        response = self.client.put(self._get_customer_url(self.customers['owner']),
                                   self._get_valid_payload())
        self.assertEqual(response.status_code, status.HTTP_200_OK, 'Error message: %s' % response.data)

        response = self.client.put(self._get_customer_url(self.customers['inaccessible']),
                                   self._get_valid_payload())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_change_single_customer_field_he_is_not_owner_of(self):
        self.client.force_authenticate(user=self.users['not_owner'])

        self._check_single_customer_field_change_permission(self.customers['inaccessible'], status.HTTP_404_NOT_FOUND)

    def test_user_cannot_change_customer_field_he_is_owner_of(self):
        self.client.force_authenticate(user=self.users['owner'])

        self._check_single_customer_field_change_permission(self.customers['owner'], status.HTTP_403_FORBIDDEN)

    def test_user_can_change_single_customer_field_if_he_is_staff(self):
        self.client.force_authenticate(user=self.users['staff'])

        self._check_single_customer_field_change_permission(self.customers['owner'], status.HTTP_200_OK)

        self._check_single_customer_field_change_permission(self.customers['inaccessible'], status.HTTP_200_OK)

    # Helper methods
    def _get_valid_payload(self, resource=None):
        resource = resource or factories.CustomerFactory()

        return {
            'name': resource.name,
            'abbreviation': resource.abbreviation,
            'contact_details': resource.contact_details,
        }

    def _check_single_customer_field_change_permission(self, customer, status_code):
        payload = self._get_valid_payload(customer)

        for field, value in payload.items():
            data = {
                field: value
            }

            response = self.client.patch(self._get_customer_url(customer), data)
            self.assertEqual(response.status_code, status_code)


class CustomerQuotasTest(test.APITransactionTestCase):

    def setUp(self):
        self.customer = factories.CustomerFactory()
        self.staff = factories.UserFactory(is_staff=True)

    def test_customer_projects_quota_increases_on_project_creation(self):
        factories.ProjectFactory(customer=self.customer)
        self.assert_quota_usage('nc_project_count', 1)

    def test_customer_projects_quota_decreases_on_project_deletion(self):
        project = factories.ProjectFactory(customer=self.customer)
        project.delete()
        self.assert_quota_usage('nc_project_count', 0)

    def test_customer_services_quota_increases_on_service_creation(self):
        factories.TestServiceFactory(customer=self.customer)
        self.assert_quota_usage('nc_service_count', 1)

    def test_customer_services_quota_decreases_on_service_deletion(self):
        service = factories.TestServiceFactory(customer=self.customer)
        service.delete()
        self.assert_quota_usage('nc_service_count', 0)

    def test_customer_and_project_service_project_link_quota_updated(self):
        self.assert_quota_usage('nc_service_project_link_count', 0)
        service = factories.TestServiceFactory(customer=self.customer)

        project1 = factories.ProjectFactory(customer=self.customer)
        factories.TestServiceProjectLinkFactory(service=service, project=project1)

        project2 = factories.ProjectFactory(customer=self.customer)
        factories.TestServiceProjectLinkFactory(service=service, project=project2)

        self.assertEqual(project1.quotas.get(name='nc_service_project_link_count').usage, 1)
        self.assertEqual(project2.quotas.get(name='nc_service_project_link_count').usage, 1)

        self.assert_quota_usage('nc_service_project_link_count', 2)
        self.assert_quota_usage('nc_service_count', 1)

        project2.delete()
        project1.delete()

        self.assert_quota_usage('nc_service_count', 1)
        self.assert_quota_usage('nc_service_project_link_count', 0)

    def test_customer_users_quota_increases_on_adding_owner(self):
        user = factories.UserFactory()
        self.customer.add_user(user, CustomerRole.OWNER)
        self.assert_quota_usage('nc_user_count', 1)

    def test_customer_users_quota_decreases_on_removing_owner(self):
        user = factories.UserFactory()
        self.customer.add_user(user, CustomerRole.OWNER)
        self.customer.remove_user(user)
        self.assert_quota_usage('nc_user_count', 0)

    def test_customer_users_quota_increases_on_adding_administrator(self):
        project = factories.ProjectFactory(customer=self.customer)
        user = factories.UserFactory()
        project.add_user(user, ProjectRole.ADMINISTRATOR)
        self.assert_quota_usage('nc_user_count', 1)

    def test_customer_users_quota_decreases_on_removing_administrator(self):
        project = factories.ProjectFactory(customer=self.customer)
        user = factories.UserFactory()
        project.add_user(user, ProjectRole.ADMINISTRATOR)
        project.remove_user(user)
        self.assert_quota_usage('nc_user_count', 0)

    def test_customer_quota_is_not_increased_on_adding_owner_as_administrator(self):
        user = factories.UserFactory()
        project = factories.ProjectFactory(customer=self.customer)
        self.customer.add_user(user, CustomerRole.OWNER)
        project.add_user(user, ProjectRole.ADMINISTRATOR)

        self.assert_quota_usage('nc_user_count', 1)

    def test_customer_quota_is_not_increased_on_adding_owner_as_manager(self):
        user = factories.UserFactory()
        project = factories.ProjectFactory(customer=self.customer)
        self.customer.add_user(user, CustomerRole.OWNER)
        project.add_user(user, ProjectRole.ADMINISTRATOR)

        self.assert_quota_usage('nc_user_count', 1)

    def test_customer_users_quota_decreases_when_one_project_is_deleted(self):
        project = factories.ProjectFactory(customer=self.customer)
        user = factories.UserFactory()

        project.add_user(user, ProjectRole.ADMINISTRATOR)
        self.assert_quota_usage('nc_user_count', 1)

        project.delete()
        self.assert_quota_usage('nc_user_count', 0)

    def test_customer_users_quota_decreases_when_projects_are_deleted_in_bulk(self):
        count = 2
        for _ in range(count):
            project = factories.ProjectFactory(customer=self.customer)
            user = factories.UserFactory()
            project.add_user(user, ProjectRole.ADMINISTRATOR)

        self.assert_quota_usage('nc_user_count', count)

        self.customer.projects.all().delete()
        self.assert_quota_usage('nc_user_count', 0)

    def assert_quota_usage(self, name, value):
        self.assertEqual(value, self.customer.quotas.get(name=name).usage)


class CustomerUnicodeTest(TransactionTestCase):
    def test_customer_can_have_unicode_name(self):
        factories.CustomerFactory(name="Моя организация")


@ddt
class CustomerUsersListTest(test.APITransactionTestCase):
    def setUp(self):
        self.fixture = fixtures.ProjectFixture()
        self.owner = self.fixture.owner
        self.admin = self.fixture.admin
        self.manager = self.fixture.manager
        self.customer = self.fixture.customer
        self.url = factories.CustomerFactory.get_url(self.customer, action='users')

    @data('staff', 'owner', 'manager', 'admin')
    def test_user_can_list_customer_users(self, user):
        self.client.force_authenticate(getattr(self.fixture, user))
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

        self.assertSetEqual({user['role'] for user in response.data}, {'owner', None, None})
        self.assertSetEqual({user['uuid'] for user in response.data},
                            {self.owner.uuid.hex, self.admin.uuid.hex, self.manager.uuid.hex})
        self.assertSetEqual({user['projects'] and user['projects'][0]['role'] or None
                             for user in response.data}, {None, 'admin', 'manager'})

    def test_user_can_not_list_project_users(self):
        self.client.force_authenticate(self.fixture.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CustomerCountersListTest(test.APITransactionTestCase):
    def setUp(self):
        self.fixture = fixtures.ServiceFixture()
        self.owner = self.fixture.owner
        self.admin = self.fixture.admin
        self.manager = self.fixture.manager
        self.customer = self.fixture.customer
        self.service = self.fixture.service
        self.url = factories.CustomerFactory.get_url(self.customer, action='counters')

    def test_user_can_get_customer_counters(self):
        self.client.force_authenticate(self.fixture.owner)
        response = self.client.get(self.url, {'fields': ['users', 'projects', 'services']})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'users': 3, 'projects': 1, 'services': 1})


class UserCustomersFilterTest(test.APITransactionTestCase):
    def setUp(self):
        self.staff = factories.UserFactory(is_staff=True)
        self.user1 = factories.UserFactory()
        self.user2 = factories.UserFactory()

        self.customer1 = factories.CustomerFactory()
        self.customer2 = factories.CustomerFactory()

        self.customer1.add_user(self.user1, CustomerRole.OWNER)
        self.customer2.add_user(self.user1, CustomerRole.OWNER)
        self.customer2.add_user(self.user2, CustomerRole.OWNER)

    def test_staff_can_filter_customer_by_user(self):
        self.assert_staff_can_filter_customer_by_user(self.user1, {self.customer1, self.customer2})
        self.assert_staff_can_filter_customer_by_user(self.user2, {self.customer2})

    def assert_staff_can_filter_customer_by_user(self, user, customers):
        self.client.force_authenticate(self.staff)
        response = self.client.get(factories.CustomerFactory.get_list_url(), {
            'user_uuid': user.uuid.hex,
            'fields': ['uuid']
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({customer['uuid'] for customer in response.data},
                         {customer.uuid.hex for customer in customers})
