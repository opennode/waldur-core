from __future__ import unicode_literals

from unittest import TestCase

from django.core.urlresolvers import reverse
from django.test import TransactionTestCase
from mock_django import mock_signal_receiver
from rest_framework import status
from rest_framework import test

from nodeconductor.structure import signals
from nodeconductor.structure.models import Customer
from nodeconductor.structure.models import CustomerRole
from nodeconductor.structure.models import ProjectRole
from nodeconductor.structure.models import ProjectGroupRole
from nodeconductor.structure.tests import factories


class UrlResolverMixin(object):
    def _get_customer_url(self, customer):
        return 'http://testserver' + reverse('customer-detail', kwargs={'uuid': customer.uuid})

    def _get_project_url(self, project):
        return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})

    def _get_project_group_url(self, project_group):
        return 'http://testserver' + reverse('projectgroup-detail', kwargs={'uuid': project_group.uuid})

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
        self.assertEqual(membership.group.customerrole.customer, self.customer)

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


class CustomerRoleTest(TestCase):
    def setUp(self):
        self.customer = factories.CustomerFactory()

    def test_owner_customer_role_is_created_upon_customer_creation(self):
        self.assertTrue(self.customer.roles.filter(role_type=CustomerRole.OWNER).exists(),
                        'Owner role should have been created')


class CustomerApiPermissionTest(UrlResolverMixin, test.APITransactionTestCase):
    def setUp(self):
        self.users = {
            'staff': factories.UserFactory(is_staff=True),
            'owner': factories.UserFactory(),
            'not_owner': factories.UserFactory(),
            'admin': factories.UserFactory(),
            'admin_other': factories.UserFactory(),
            'manager': factories.UserFactory(),
            'group_manager': factories.UserFactory(),
        }

        self.customers = {
            'owned': factories.CustomerFactory.create_batch(2),
            'inaccessible': factories.CustomerFactory.create_batch(2),
            'admin': factories.CustomerFactory(),
            'manager': factories.CustomerFactory(),
            'group_manager': factories.CustomerFactory(),
        }

        for customer in self.customers['owned']:
            customer.add_user(self.users['owner'], CustomerRole.OWNER)

        self.projects = {
            'admin': factories.ProjectFactory(customer=self.customers['admin']),
            'manager': factories.ProjectFactory(customer=self.customers['manager']),
            'group_manager': factories.ProjectFactory(customer=self.customers['group_manager']),
        }

        self.projects['admin'].add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)
        self.projects['manager'].add_user(self.users['manager'], ProjectRole.MANAGER)

        self.project_groups = {
            'admin': factories.ProjectGroupFactory(customer=self.customers['admin']),
            'manager': factories.ProjectGroupFactory(customer=self.customers['manager']),
            'group_manager': factories.ProjectGroupFactory(customer=self.customers['group_manager']),
        }

        self.project_groups['admin'].projects.add(self.projects['admin'])
        self.project_groups['manager'].projects.add(self.projects['manager'])
        self.project_groups['group_manager'].projects.add(self.projects['group_manager'])
        self.project_groups['group_manager'].add_user(self.users['group_manager'], ProjectGroupRole.MANAGER)

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

    def test_user_can_list_customer_if_he_is_group_manager_in_a_project_group_owned_by_a_customer(self):
        self.client.force_authenticate(user=self.users['group_manager'])
        self._check_customer_in_list(self.customers['group_manager'])

    def test_user_cannot_list_customer_if_he_is_admin_in_a_project_not_owned_by_a_customer(self):
        self.client.force_authenticate(user=self.users['admin'])
        self._check_customer_in_list(self.customers['manager'], False)

    def test_user_cannot_list_customer_if_he_is_manager_in_a_project_not_owned_by_a_customer(self):
        self.client.force_authenticate(user=self.users['manager'])
        self._check_customer_in_list(self.customers['admin'], False)

    def test_user_cannot_list_customer_if_he_is_group_manager_in_a_project_group_not_owned_by_a_customer(self):
        self.client.force_authenticate(user=self.users['group_manager'])
        self._check_customer_in_list(self.customers['manager'], False)

    # Nested objects filtration tests
    def test_user_can_see_project_he_has_a_role_in_within_customer(self):
        for user_role in ('admin', 'manager', 'group_manager'):
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

    def test_user_can_see_project_group_he_has_a_role_in_within_customer(self):
        for user_role in ('admin', 'manager', 'group_manager'):
            self.client.force_authenticate(user=self.users[user_role])

            customer = self.customers[user_role]

            seen_project_group = self.project_groups[user_role]

            response = self.client.get(self._get_customer_url(customer))
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            project_group_urls = set([pgrp['url'] for pgrp in response.data['project_groups']])
            self.assertIn(
                self._get_project_group_url(seen_project_group), project_group_urls,
                'User should see project group',
            )

    def test_user_cannot_see_project_groups_from_different_customer(self):
        # setUp
        project_group_1_1 = self.project_groups['admin']
        project_group_1_2 = factories.ProjectGroupFactory(customer=self.customers['admin'])

        project_group_2_1 = self.project_groups['manager']
        project_group_2_2 = factories.ProjectGroupFactory(customer=self.customers['manager'])

        self.projects['manager'].add_user(self.users['admin'], ProjectRole.MANAGER)

        # test body
        self.client.force_authenticate(user=self.users['admin'])
        response = self.client.get(self._get_customer_url(self.customers['admin']))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        project_group_urls = set([project_group['url'] for project_group in response.data['project_groups']])

        self.assertIn(
            self._get_project_group_url(project_group_1_1), project_group_urls,
            'User should see project group {0}'.format(project_group_1_1),
        )

        for project_group in (
                project_group_1_2,
                project_group_2_1,
                project_group_2_2,
        ):
            self.assertNotIn(
                self._get_project_group_url(project_group), project_group_urls,
                'User should not see project group {0}'.format(project_group),
            )

    def test_user_cannot_see_project_he_has_no_role_in_within_customer(self):
        for user_role in ('admin', 'manager', 'group_manager'):
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

    def test_user_cannot_see_project_group_he_has_no_role_in_within_customer(self):
        for user_role in ('admin', 'manager', 'group_manager'):
            self.client.force_authenticate(user=self.users[user_role])

            customer = self.customers[user_role]

            non_seen_project = factories.ProjectFactory(customer=customer)
            non_seen_project_group = factories.ProjectGroupFactory(customer=customer)
            non_seen_project_group.projects.add(non_seen_project)

            response = self.client.get(self._get_customer_url(customer))
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            project_group_urls = set([pgrp['url'] for pgrp in response.data['project_groups']])
            self.assertNotIn(
                self._get_project_group_url(non_seen_project_group), project_group_urls,
                'User should not see project group',
            )

    # Direct instance access tests
    def test_user_can_access_customers_he_is_owner_of(self):
        self.client.force_authenticate(user=self.users['owner'])

        self._check_user_direct_access_customer(self.customers['owned'], status.HTTP_200_OK)

    def test_user_can_see_its_owner_membership_in_a_cloud_he_is_owner_of(self):
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

    def test_user_can_delete_customer_without_associated_project_groups_and_projects_if_he_is_staff(self):
        self.client.force_authenticate(user=self.users['staff'])

        response = self.client.delete(self._get_customer_url(self.customers['owner']))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.delete(self._get_customer_url(self.customers['inaccessible']))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_user_cannot_delete_customer_with_associated_project_groups_if_he_is_staff(self):
        self.client.force_authenticate(user=self.users['staff'])

        for customer in self.customers.values():
            factories.ProjectGroupFactory(customer=customer)

            response = self.client.delete(self._get_customer_url(customer))

            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
            self.assertDictContainsSubset({'detail': 'Cannot delete customer with existing project_groups'},
                                          response.data)

    def test_user_cannot_delete_customer_with_associated_projects_if_he_is_staff(self):
        self.client.force_authenticate(user=self.users['staff'])

        for customer in self.customers.values():
            factories.ProjectFactory(customer=customer)

            response = self.client.delete(self._get_customer_url(customer))

            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
            self.assertDictContainsSubset({'detail': 'Cannot delete customer with existing projects'},
                                          response.data)


    # Creation tests
    def test_user_cannot_create_customer_if_he_is_not_staff(self):
        self.client.force_authenticate(user=self.users['not_owner'])

        response = self.client.post(reverse('customer-list'), self._get_valid_payload())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

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
        self.assertEqual(response.status_code, status.HTTP_200_OK)

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
