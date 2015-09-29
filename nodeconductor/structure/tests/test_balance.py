from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework import test

from nodeconductor.structure.tests.factories import CustomerFactory, UserFactory
from nodeconductor.structure.models import BalanceHistory
from nodeconductor.structure.models import CustomerRole


class BalanceHistoryTest(TestCase):
    def setUp(self):
        self.delta = 10
        self.amount = 100
        self.customer = CustomerFactory(balance=self.amount)

    def test_empty_history(self):
        self.assertFalse(BalanceHistory.objects.filter(customer=self.customer).exists())

    def test_when_customer_credited_history_record_created(self):
        self.customer.credit_account(self.delta)
        self.assert_balance_equals(self.amount + self.delta)

    def test_when_customer_debited_history_record_created(self):
        self.customer.debit_account(self.delta)
        self.assert_balance_equals(self.amount - self.delta)

    def assert_balance_equals(self, amount):
        self.assertEqual(amount, BalanceHistory.objects.get(customer=self.customer).amount)


class BalanceHistoryViewTest(test.APITransactionTestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other = UserFactory()
        self.customer = CustomerFactory()
        self.customer.add_user(self.user, CustomerRole.OWNER)

    def test_other_user_can_not_see_balance_history(self):
        self.client.force_authenticate(user=self.other)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_see_balance_history(self):
        amounts = [10, 15, 20, 25]
        for amount in amounts:
            BalanceHistory.objects.create(
                customer=self.customer, amount=amount, created=timezone.now() - timedelta(days=1))

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.get_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_equal_decimals(amounts, [item['amount'] for item in response.data])

    def test_balance_history_displayed_for_last_month(self):
        BalanceHistory.objects.create(customer=self.customer, amount=10)
        BalanceHistory.objects.create(
            customer=self.customer, amount=20, created=timezone.now() - timedelta(weeks=6))

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.get_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_equal_decimals([10], [item['amount'] for item in response.data])

    def get_url(self):
        return CustomerFactory.get_url(self.customer, 'balance_history')

    def assert_equal_decimals(self, xs, ys):
        self.assertEqual(map(Decimal, xs), map(Decimal, ys))
