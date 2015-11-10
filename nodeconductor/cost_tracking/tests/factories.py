import factory

from django.core.urlresolvers import reverse
from django.contrib.contenttypes.models import ContentType

from nodeconductor.cost_tracking import models
from nodeconductor.openstack import models as openstack_models
from nodeconductor.openstack.tests import factories as openstack_factories
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


class AbstractPriceListItemFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.AbstractPriceListItem
        abstract = True

    resource_content_type = factory.LazyAttribute(
        lambda _: ContentType.objects.get_for_model(openstack_models.Instance))

    key = factory.Sequence(lambda n: 'price list item %s' % n)
    value = factory.Iterator([10, 100, 1000, 10000, 1313, 13])
    item_type = factory.Iterator(['flavor', 'storage'])
    units = factory.Iterator(['USD', 'EUR', 'UAH', 'OMR'])


class PriceListItemFactory(AbstractPriceListItemFactory):
    class Meta(object):
        model = models.PriceListItem

    service = factory.SubFactory(openstack_factories.OpenStackServiceFactory)

    @classmethod
    def get_list_url(self):
        return 'http://testserver' + reverse('pricelistitem-list')

    @classmethod
    def get_url(self, price_list_item, action=None):
        if price_list_item is None:
            price_list_item = PriceListItemFactory()
        url = 'http://testserver' + reverse('pricelistitem-detail', kwargs={'uuid': price_list_item.uuid})
        return url if action is None else url + action + '/'


class DefaultPriceListItemFactory(AbstractPriceListItemFactory):
    class Meta(object):
        model = models.DefaultPriceListItem

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
