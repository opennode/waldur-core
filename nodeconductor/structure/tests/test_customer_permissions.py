from __future__ import unicode_literals

import collections

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework import test
from rest_framework.reverse import reverse

from nodeconductor.structure.models import CustomerRole
from nodeconductor.structure.tests import factories

User = get_user_model()

TestRole = collections.namedtuple('TestRole', ['user', 'customer', 'role'])


class CustomerPermissionApiPermissionTest(test.APITransactionTestCase):
    all_roles = (
        # user customer role
        TestRole('first', 'first', 'owner'),

        TestRole('both', 'first', 'owner'),
        TestRole('both', 'second', 'owner'),
    )

    role_map = {
        'owner': CustomerRole.OWNER,
    }

    def setUp(self):
        self.users = {
            # 'staff': factories.UserFactory(is_staff=True),
            'first': factories.UserFactory(),
            'both': factories.UserFactory(),
            'no_role': factories.UserFactory(),
        }

        self.customers = {
            'first': factories.CustomerFactory(),
            'second': factories.CustomerFactory(),
        }

        for user, customer, role in self.all_roles:
            self.customers[customer].add_user(self.users[user], self.role_map[role])

    # No role tests
    def test_user_cannot_list_roles_within_customers_he_has_no_role_in(self):
        for login_user in self.users:
            self.client.force_authenticate(user=self.users[login_user])

            response = self.client.get(reverse('customer_permission-list'))
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            users_customers = set(r.customer for r in self.all_roles if r.user == login_user)
            unseen_roles = (r for r in self.all_roles if r.customer not in users_customers)

            for role in unseen_roles:
                role_url = self._get_permission_url(*role)

                urls = set([role['url'] for role in response.data])

                self.assertNotIn(
                    role_url, urls,
                    '{0} user sees privilege he is not supposed to see: {1}'.format(login_user, role),
                )

    # Customer owner tests
    def test_user_can_list_roles_within_customers_he_owns(self):
        for login_user in self.users:
            self.client.force_authenticate(user=self.users[login_user])

            response = self.client.get(reverse('customer_permission-list'))
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            users_customers = set(r.customer for r in self.all_roles if r.user == login_user)
            seen_roles = (r for r in self.all_roles if r.customer in users_customers)

            for role in seen_roles:
                role_url = self._get_permission_url(*role)

                urls = set([role['url'] for role in response.data])

                self.assertIn(
                    role_url, urls,
                    '{0} user does not see privilege he is supposed to see: {1}'.format(login_user, role),
                )

    # Helper methods
    def _get_permission_url(self, user, customer, role):
        permission = User.groups.through.objects.get(
            user=self.users[user],
            group__customerrole__role_type=self.role_map[role],
            group__customerrole__customer=self.customers[customer],
        )
        return 'http://testserver' + reverse('customer_permission-detail', kwargs={'pk': permission.pk})
