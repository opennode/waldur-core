from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from nodeconductor.cost_tracking import models, CostTrackingBackend
from nodeconductor.cost_tracking.tests import factories
from nodeconductor.structure.tests.factories import TestInstanceFactory


class CostEstimateTest(TestCase):
    def setUp(self):
        self.resource = TestInstanceFactory()
        self.service = self.resource.service_project_link.service
        self.content_type = ContentType.objects.get_for_model(self.resource)
        self.default_item = factories.DefaultPriceListItemFactory(resource_content_type=self.content_type)

    def test_cost_estimate_is_calculated_using_default_item(self):
        monthly_usage = 10
        used_items = [(self.default_item.item_type, self.default_item.key, monthly_usage)]
        backend = self.get_dummy_backend(used_items)

        total_cost = monthly_usage * Decimal(self.default_item.monthly_rate)
        self.assertEqual(total_cost, backend.get_monthly_cost_estimate(self.resource))

    def test_cost_estimate_is_calculated_using_service_price_list_item(self):
        service_item = models.PriceListItem.objects.create(
            service=self.service,
            default_price_list_item=self.default_item,
            value=100
        )

        monthly_usage = 10
        used_items = [(self.default_item.item_type, self.default_item.key, monthly_usage)]
        backend = self.get_dummy_backend(used_items)

        total_cost = monthly_usage * Decimal(service_item.monthly_rate)
        self.assertEqual(total_cost, backend.get_monthly_cost_estimate(self.resource))

    def get_dummy_backend(self, used_items):
        class DummyCostTrackingBackend(CostTrackingBackend):
            @classmethod
            def get_used_items(cls, resource):
                return used_items
        return DummyCostTrackingBackend
