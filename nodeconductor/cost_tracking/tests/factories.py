import factory

from django.core.urlresolvers import reverse
from django.contrib.contenttypes.models import ContentType

from nodeconductor.cost_tracking import models, CostTrackingStrategy
from nodeconductor.structure.tests import models as test_models
from nodeconductor.structure.tests import factories as structure_factories


class PriceEstimateFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.PriceEstimate

    scope = factory.SubFactory(structure_factories.ProjectFactory)
    total = factory.Iterator([10, 100, 1000, 10000, 980, 42])
    month = factory.Iterator(range(1, 13))
    year = factory.Iterator(range(2012, 2016))

    @classmethod
    def get_list_url(self):
        return 'http://testserver' + reverse('priceestimate-list')

    @classmethod
    def get_url(self, price_estimate, action=None):
        if price_estimate is None:
            price_estimate = PriceEstimateFactory()
        url = 'http://testserver' + reverse('priceestimate-detail', kwargs={'uuid': price_estimate.uuid})
        return url if action is None else url + action + '/'


class ConsumptionDetailsFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.ConsumptionDetails

    price_estimate = factory.SubFactory(PriceEstimateFactory)


class AbstractPriceListItemFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.AbstractPriceListItem
        abstract = True

    value = factory.Iterator([10, 100, 1000, 10000, 1313, 13])
    units = factory.Iterator(['USD', 'EUR', 'UAH', 'OMR'])


class DefaultPriceListItemFactory(AbstractPriceListItemFactory):
    class Meta(object):
        model = models.DefaultPriceListItem

    resource_content_type = factory.LazyAttribute(
        lambda _: ContentType.objects.get_for_model(test_models.TestInstance))

    key = factory.Sequence(lambda n: 'price list item %s' % n)
    item_type = factory.Iterator(['flavor', 'storage'])

    @classmethod
    def get_list_url(self):
        return 'http://testserver' + reverse('defaultpricelistitem-list')

    @classmethod
    def get_url(self, default_price_list_item, action=None):
        if default_price_list_item is None:
            default_price_list_item = DefaultPriceListItemFactory()
        url = 'http://testserver' + reverse(
            'defaultpricelistitem-detail', kwargs={'uuid': default_price_list_item.uuid})
        return url if action is None else url + action + '/'


class PriceListItemFactory(AbstractPriceListItemFactory):
    class Meta(object):
        model = models.PriceListItem

    service = factory.SubFactory(structure_factories.TestServiceFactory)
    default_price_list_item = factory.SubFactory(DefaultPriceListItemFactory)

    @classmethod
    def get_list_url(self):
        return 'http://testserver' + reverse('pricelistitem-list')

    @classmethod
    def get_url(self, price_list_item, action=None):
        if price_list_item is None:
            price_list_item = PriceListItemFactory()
        url = 'http://testserver' + reverse('pricelistitem-detail', kwargs={'uuid': price_list_item.uuid})
        return url if action is None else url + action + '/'


class TestNewInstanceCostTrackingStrategy(CostTrackingStrategy):
    resource_class = test_models.TestNewInstance

    class Types(object):
        STORAGE = 'storage'
        RAM = 'ram'
        CORES = 'cores'
        QUOTAS = 'quotas'
        FLAVOR = 'flavor'

    @classmethod
    def get_consumables(cls, resource):
        States = test_models.TestNewInstance.States
        consumables = {
            '%s: 1 MB' % cls.Types.STORAGE: resource.disk if resource.state != States.ERRED else 0,
            '%s: 1 MB' % cls.Types.RAM: resource.ram if resource.runtime_state == 'online' else 0,
            '%s: 1 core' % cls.Types.CORES: resource.cores if resource.runtime_state == 'online' else 0,
            '%s: test_quota' % cls.Types.FLAVOR: resource.quotas.get(name=test_models.TestNewInstance.Quotas.test_quota).usage,
        }
        if resource.flavor_name and resource.state != States.ERRED:
            consumables[('%s: %s' % (cls.Types.FLAVOR, resource.flavor_name))] = 1
        return consumables

    @classmethod
    def get_consumables_default_prices(cls):
        return [
            {"item_type": cls.Types.STORAGE, "key": "1 MB", "units": "MB", "rate": 0.5, "name": "Storage"},
            {"item_type": cls.Types.RAM, "key": "1 MB", "units": "MB", "rate": 1, "name": "RAM"},
            {"item_type": cls.Types.CORES, "key": "1 core", "units": "", "rate": 10, "name": "Cores"},
            {"item_type": cls.Types.QUOTAS, "key": "test_quota", "units": "", "rate": 2, "name": "Test quota"},
            {"item_type": cls.Types.FLAVOR, "key": "small", "units": "", "rate": 20, "name": "Small flavor"},
            {"item_type": cls.Types.FLAVOR, "key": "medium", "units": "", "rate": 40, "name": "Medium flavor"},
            {"item_type": cls.Types.FLAVOR, "key": "large", "units": "", "rate": 60, "name": "Large flavor"},
        ]
