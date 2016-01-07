import unittest
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from nodeconductor.cost_tracking import models
from nodeconductor.cost_tracking.tests import factories
from nodeconductor.openstack import models as openstack_models
from nodeconductor.openstack.tests import factories as openstack_factories


class PriceListItemsHandlersTest(TestCase):

    def setUp(self):
        self.service = openstack_factories.OpenStackServiceFactory()
        self.openstack_resource_content_type = ContentType.objects.get_for_model(openstack_models.OpenStackService)

    @unittest.skip('Disabling till price list items are used in practice')
    def test_new_price_list_item_will_be_created_on_default_item_creation(self):
        default_item = factories.DefaultPriceListItemFactory(resource_content_type=self.openstack_resource_content_type)

        self.assertTrue(models.PriceListItem.objects.filter(
            service=self.service,
            key=default_item.key,
            value=default_item.value,
            units=default_item.units,
            item_type=default_item.item_type).exists()
        )

    @unittest.skip('Disabling till price list items are used in practice')
    def test_price_list_item_will_be_changed_on_default_item_change(self):
        default_item = factories.DefaultPriceListItemFactory(resource_content_type=self.openstack_resource_content_type)

        default_item.key = 'new_key'
        default_item.save()

        self.assertTrue(models.PriceListItem.objects.filter(
            service=self.service,
            key=default_item.key,
            value=default_item.value,
            units=default_item.units,
            item_type=default_item.item_type).exists()
        )

    @unittest.skip('Disabling till price list items are used in practice')
    def test_manually_created_price_list_item_value_will_not_be_changed_on_default_item_value_change(self):
        default_item = factories.DefaultPriceListItemFactory(resource_content_type=self.openstack_resource_content_type)
        item = models.PriceListItem.objects.get(
            service=self.service, key=default_item.key, item_type=default_item.item_type)
        item.is_manually_input = True
        item.save()

        default_item.value = 666
        default_item.save()

        reread_item = models.PriceListItem.objects.get(id=item.id)
        self.assertEqual(item.value, reread_item.value)

    @unittest.skip('Disabling till price list items are used in practice')
    def test_manually_created_price_list_item_key_will_not_be_changed_on_default_item_key_change(self):
        default_item = factories.DefaultPriceListItemFactory(resource_content_type=self.openstack_resource_content_type)
        item = models.PriceListItem.objects.get(
            service=self.service, key=default_item.key, item_type=default_item.item_type)
        item.is_manually_input = True
        item.save()

        default_item.key = 'new_key'
        default_item.save()

        reread_item = models.PriceListItem.objects.get(id=item.id)
        self.assertEqual(default_item.key, reread_item.key)

    @unittest.skip('Disabling till price list items are used in practice')
    def test_price_list_item_will_be_deleted_if_default_item_deleted(self):
        default_item = factories.DefaultPriceListItemFactory(resource_content_type=self.openstack_resource_content_type)
        item = models.PriceListItem.objects.get(
            service=self.service, key=default_item.key, item_type=default_item.item_type)

        default_item.delete()

        self.assertFalse(models.PriceListItem.objects.filter(id=item.id).exists())

    def test_ancestor_price_estimate_will_be_decreased_after_descendor_deletion(self):
        instance = openstack_factories.InstanceFactory()
        total = 77
        month = 10
        year = 2015
        models.PriceEstimate.update_price_for_scope(instance, month, year, total)

        instance.delete()

        project = instance.service_project_link.project
        self.assertEqual(models.PriceEstimate.objects.get(scope=project, month=month, year=year).total, 0)
        self.assertEqual(models.PriceEstimate.objects.get(scope=project.customer, month=month, year=year).total, 0)
