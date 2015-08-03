from django.test import TestCase

from nodeconductor.cost_tracking import models
from nodeconductor.oracle.tests import factories as oracle_factories


class PriceListItemsHandlersTest(TestCase):

    def test_price_list_are_created_for_new_service(self):
        service = oracle_factories.OracleServiceFactory()

        for key, item_type in models.PriceKeysRegister.get_keys_with_types_for_service(service):
            self.assertTrue(models.PriceListItem.objects.filter(
                service=service, key=key, item_type=item_type).exists())

    def test_resource_are_connected_to_service_items(self):
        resource = oracle_factories.DatabaseFactory()

        for key, item_type in models.PriceKeysRegister.get_keys_with_types_for_resource(resource):
            item = models.PriceListItem.objects.get(
                service=resource.service_project_link.service, key=key, item_type=item_type)
            self.assertTrue(models.ResourcePriceItem.objects.filter(item=item, resource=resource))
