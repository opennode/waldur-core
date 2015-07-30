import factory

from django.core.urlresolvers import reverse

from nodeconductor.cost_tracking import models
from nodeconductor.oracle.tests import factories as oracle_factories
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


class PriceListFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.PriceList

    service = factory.SubFactory(oracle_factories.OracleServiceFactory)

    @factory.post_generation
    def items(self, create, extracted, **kwargs):
        if create:
            if extracted:
                for item in extracted:
                    self.items.create(**item)
            else:
                for _ in range(2):
                    PriceListItemFactory(price_list=self)

    @classmethod
    def get_list_url(self):
        return 'http://testserver' + reverse('pricelist-list')

    @classmethod
    def get_url(self, price_list, action=None):
        if price_list is None:
            price_list = PriceListFactory()
        url = 'http://testserver' + reverse('pricelist-detail', kwargs={'uuid': price_list.uuid})
        return url if action is None else url + action + '/'


class PriceListItemFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.PriceListItem

    price_list = factory.SubFactory(PriceListFactory)
    name = factory.Iterator(['cpu', 'memory', 'storage'])
    value = factory.Iterator([10, 100, 1000, 10000, 1313, 13])
