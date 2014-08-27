from __future__ import unicode_literals

from unittest import TestCase

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.structure.models import CustomerRole
from nodeconductor.structure.tests import factories


class UrlResolverMixin(object):
    def _get_customer_url(self, customer):
        return 'http://testserver' + reverse('customer-detail', kwargs={'uuid': customer.uuid})


class CustomerRoleTest(TestCase):
    def setUp(self):
        self.customer = factories.CustomerFactory()

    def test_owner_customer_role_is_created_upon_customer_creation(self):
        self.assertTrue(self.customer.roles.filter(role_type=CustomerRole.OWNER).exists(),
                        'Owner role should have been created')


class CustomerApiPermissionTest(UrlResolverMixin, test.APISimpleTestCase):
    def setUp(self):
        user = factories.UserFactory()
        self.client.force_authenticate(user=user)

        self.customers = {
            'owned': factories.CustomerFactory.create_batch(2),
            'inaccessible': factories.ProjectGroupFactory.create_batch(2),
        }

        for customer in self.customers['owned']:
            customer.add_user(user, CustomerRole.OWNER)

    # List filtration tests
    def test_user_can_list_customers_he_is_owner_of(self):
        response = self.client.get(reverse('customer-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        urls = set([instance['url'] for instance in response.data])
        for customer in self.customers['owned']:
            url = self._get_customer_url(customer)

            self.assertIn(url, urls)

    def test_user_cannot_list_customers_he_is_not_owner_of(self):
        response = self.client.get(reverse('customer-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        urls = set([instance['url'] for instance in response.data])
        for customer in self.customers['inaccessible']:
            url = self._get_customer_url(customer)

            self.assertNotIn(url, urls)

    # Direct instance access tests
    def test_user_can_access_customers_he_is_owner_of(self):
        for customer in self.customers['owned']:
            response = self.client.get(self._get_customer_url(customer))
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_access_customers_he_is_not_owner_of(self):
        for customer in self.customers['inaccessible']:
            response = self.client.get(self._get_customer_url(customer))
            # 404 is used instead of 403 to hide the fact that the resource exists at all
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CustomerApiManipulationTest(UrlResolverMixin, test.APISimpleTestCase):
    def setUp(self):
        self.user = factories.UserFactory()
        self.client.force_authenticate(user=self.user)

        self.customer = factories.CustomerFactory()
        self.customer_url = self._get_customer_url(self.customer)

    def test_cannot_delete_customer(self):
        response = self.client.delete(self.customer_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_create_customer(self):
        response = self.client.post(self.customer_url, self._get_valid_payload())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_change_customer_as_whole(self):
        response = self.client.put(self.customer_url, self._get_valid_payload(self.customer))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_change_single_customer_field(self):
        payload = self._get_valid_payload(self.customer)

        for field, value in payload.items():
            data = {
                field: value
            }

            response = self.client.patch(self.customer_url, data)

            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def _get_valid_payload(self, resource=None):
        resource = resource or factories.CustomerFactory()

        return {
            'name': resource.name,
            'abbreviation': resource.abbreviation,
            'contact_details': resource.contact_details,
        }
