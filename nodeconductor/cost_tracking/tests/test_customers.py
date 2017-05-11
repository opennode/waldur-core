from django.utils import timezone
from rest_framework import status, test

from nodeconductor.structure.tests import factories as structure_factories, fixtures as structure_fixtures
from nodeconductor.cost_tracking import models

from . import factories


class CustomerListTest(test.APITransactionTestCase):
    def setUp(self):
        self.fixture = structure_fixtures.CustomerFixture()
        self.client.force_authenticate(self.fixture.staff)

    def test_customer_price_estimate_is_exposed_on_api(self):
        expected_threshold = 100
        expected_limit = -1
        expected_total = 250
        now = timezone.now()
        factories.PriceEstimateFactory(scope=self.fixture.customer,
                                       month=now.month,
                                       year=now.year,
                                       total=expected_total,
                                       limit=expected_limit,
                                       threshold=expected_threshold)

        response = self.client.get(structure_factories.CustomerFactory.get_url(self.fixture.customer))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['price_estimate']['threshold'], expected_threshold)
        self.assertEqual(response.data['price_estimate']['limit'], expected_limit)
        self.assertEqual(response.data['price_estimate']['total'], expected_total)

    def test_customer_price_estimate_has_default_value_if_price_item_is_missing(self):
        self.assertFalse(models.PriceEstimate.objects.filter(scope=self.fixture.customer).exists())

        response = self.client.get(structure_factories.CustomerFactory.get_url(self.fixture.customer))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['price_estimate']['threshold'], 0)
        self.assertEqual(response.data['price_estimate']['limit'], -1)
        self.assertEqual(response.data['price_estimate']['total'], 0)
