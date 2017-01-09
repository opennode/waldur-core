from datetime import timedelta
from decimal import Decimal

from ddt import data, ddt
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework import test

from nodeconductor.structure.tests import fixtures
from nodeconductor.structure.tests.factories import CustomerFactory
from nodeconductor.structure.models import BalanceHistory


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


@ddt
class BalanceHistoryViewTest(test.APITransactionTestCase):
    def setUp(self):
        self.fixture = fixtures.CustomerFixture()

    def test_other_user_can_not_see_balance_history(self):
        self.client.force_authenticate(user=self.fixture.user)
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @data('owner', 'customer_support', 'staff', 'global_support')
    def test_user_can_see_balance_history(self, user):
        amounts = [10, 15, 20, 25]
        for amount in amounts:
            BalanceHistory.objects.create(
                customer=self.fixture.customer, amount=amount, created=timezone.now() - timedelta(days=1))

        self.client.force_authenticate(user=getattr(self.fixture, user))
        response = self.client.get(self.get_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_equal_decimals(amounts, [item['amount'] for item in response.data])

    def test_balance_history_displayed_for_last_month(self):
        BalanceHistory.objects.create(
            customer=self.fixture.customer, amount=10, created=timezone.now() - timedelta(days=1))
        BalanceHistory.objects.create(
            customer=self.fixture.customer, amount=20, created=timezone.now() - timedelta(days=60))

        self.client.force_authenticate(user=self.fixture.owner)
        response = self.client.get(self.get_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_equal_decimals([10], [item['amount'] for item in response.data])

    def get_url(self):
        return CustomerFactory.get_url(self.fixture.customer, 'balance_history')

    def assert_equal_decimals(self, xs, ys):
        self.assertEqual(map(Decimal, xs), map(Decimal, ys))
