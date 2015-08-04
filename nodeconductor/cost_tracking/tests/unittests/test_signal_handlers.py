from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from nodeconductor.cost_tracking import models
from nodeconductor.cost_tracking.tests import factories
from nodeconductor.oracle import models as oracle_models
from nodeconductor.oracle.tests import factories as oracle_factories


class PriceListItemsHandlersTest(TestCase):

    def setUp(self):
        self.service = oracle_factories.OracleServiceFactory()
        self.oracle_service_content_type = ContentType.objects.get_for_model(oracle_models.OracleService)

    def test_new_price_list_item_will_be_created_on_default_item_creation(self):
        default_item = factories.DefaultPriceListItemFactory(service_content_type=self.oracle_service_content_type)

        self.assertTrue(models.PriceListItem.objects.filter(
            service=self.service,
            key=default_item.key,
            value=default_item.value,
            units=default_item.units,
            item_type=default_item.item_type).exists()
        )

    def test_price_list_item_will_be_changed_on_default_item_change(self):
        default_item = factories.DefaultPriceListItemFactory(service_content_type=self.oracle_service_content_type)

        default_item.key = 'new_key'
        default_item.save()

        self.assertTrue(models.PriceListItem.objects.filter(
            service=self.service,
            key=default_item.key,
            value=default_item.value,
            units=default_item.units,
            item_type=default_item.item_type).exists()
        )

    def test_manually_created_price_list_item_value_will_not_be_changed_on_default_item_value_change(self):
        default_item = factories.DefaultPriceListItemFactory(service_content_type=self.oracle_service_content_type)
        item = models.PriceListItem.objects.get(
            service=self.service, key=default_item.key, item_type=default_item.item_type)
        item.is_manually_input = True
        item.save()

        default_item.value = 666
        default_item.save()

        reread_item = models.PriceListItem.objects.get(id=item.id)
        self.assertEqual(item.value, reread_item.value)

    def test_manually_created_price_list_item_key_will_not_be_changed_on_default_item_key_change(self):
        default_item = factories.DefaultPriceListItemFactory(service_content_type=self.oracle_service_content_type)
        item = models.PriceListItem.objects.get(
            service=self.service, key=default_item.key, item_type=default_item.item_type)
        item.is_manually_input = True
        item.save()

        default_item.key = 'new_key'
        default_item.save()

        reread_item = models.PriceListItem.objects.get(id=item.id)
        self.assertEqual(default_item.key, reread_item.key)
