from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from nodeconductor.cost_tracking import models
from nodeconductor.cost_tracking.tests import factories
from nodeconductor.openstack import models as openstack_models
from nodeconductor.openstack.tests import factories as openstack_factories


class PriceListItemsHandlersTest(TestCase):

    def setUp(self):
        self.service = openstack_factories.OpenStackServiceFactory()
        content_type = ContentType.objects.get_for_model(openstack_models.Instance)
        self.default_item = factories.DefaultPriceListItemFactory(resource_content_type=content_type)

        self.item = models.PriceListItem.objects.create(
            service=self.service,
            key=self.default_item.key,
            value=self.default_item.value,
            units=self.default_item.units,
            item_type=self.default_item.item_type,
            resource_content_type=content_type
        )

    def test_price_list_item_will_be_changed_on_default_item_change(self):
        self.default_item.key = 'new_key'
        self.default_item.save()

        self.assertTrue(models.PriceListItem.objects.filter(
            service=self.service,
            key=self.default_item.key,
            value=self.default_item.value,
            units=self.default_item.units,
            item_type=self.default_item.item_type).exists()
        )

    def test_manually_created_price_list_item_value_will_not_be_changed_on_default_item_value_change(self):
        self.item.is_manually_input = True
        self.item.save()

        self.default_item.value = 666
        self.default_item.save()

        reread_item = models.PriceListItem.objects.get(id=self.item.id)
        self.assertEqual(self.item.value, reread_item.value)

    def test_manually_created_price_list_item_key_will_not_be_changed_on_default_item_key_change(self):
        self.item.is_manually_input = True
        self.item.save()

        self.default_item.key = 'new_key'
        self.default_item.save()

        reread_item = models.PriceListItem.objects.get(id=self.item.id)
        self.assertEqual(self.default_item.key, reread_item.key)

    def test_price_list_item_will_be_deleted_if_default_item_deleted(self):
        self.default_item.delete()
        self.assertFalse(models.PriceListItem.objects.filter(id=self.item.id).exists())
