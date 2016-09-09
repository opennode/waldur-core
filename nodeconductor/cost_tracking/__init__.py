"""
Cost tracking - add-on for NC plugins.
Allows to calculate price estimates for resources from your plugin.

Check developer guide for more details.
"""
import logging
from decimal import Decimal

from django.db.models import Prefetch

from nodeconductor.structure import ServiceBackendNotImplemented


default_app_config = 'nodeconductor.cost_tracking.apps.CostTrackingConfig'
logger = logging.getLogger(__name__)


class ConsumableItem(object):

    def __init__(self, item_type, key, name=None, units='', default_price=0):
        self.item_type = item_type
        self.key = key
        self.default_price = default_price
        self.name = name if name is not None else '%s: %s' % (item_type, key)
        self.units = units

    def __repr__(self):
        return 'ConsumableItem(%s)' % self.name

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash((self.item_type, self.key))

    def __eq__(self, other):
        return (self.item_type, self.key) == (other.item_type, other.key)

    def __ne__(self, other):
        # Not strictly necessary, but to avoid having both x==y and x!=y True at the same time
        return not(self == other)


class CostTrackingStrategy(object):
    """ Describes all methods that should be implemented to enable cost
        tracking for particular resource.
    """
    resource_class = NotImplemented

    @classmethod
    def get_configuration(cls, resource):
        """ Return dictionary of consumables that are used by resource.

            Dictionary key - ConsumableItem instance.
            Dictionary value - how many units of consumable is used by resource.
            Example: {
                ConsumableItem('storage', '1 MB'): 10240,
                ConsumableItem('flavor', 'small'): 1,
                ...
            }
        """
        return {}

    @classmethod
    def get_consumable_items(cls):
        """ Return list of all possible consumed items.

            Output format:
            [
                ConsumableItem(
                    item_type=<type of consumable>,
                    key=<consumable name>,
                    name=<item pretty name, that will be visible for user>,
                    units=<consumable units (MB, GB, points, etc.>,
                    default_price=<price for consumable usage per hour>,
                )
                ...
            ]
            Output example:
            [
                ConsumableItem(
                    item_type="storage"
                    key="1 MB",
                    units="MB",
                    name="1 MB of storage",
                    default_price=0.5,
                ),
                ConsumableItem(
                    item_type="flavor"
                    key="small",
                    name="Small flavor",
                ),
                ...
            ]
        """
        return []


class ResourceNotRegisteredError(TypeError):
    pass


class CostTrackingRegister(object):
    """ Register of all connected NC plugins """

    _register = {}  # deprecated
    registered_resources = {}

    @classmethod
    def register_strategy(cls, strategy):
        cls.registered_resources[strategy.resource_class] = strategy

    @classmethod
    def _get_strategy(cls, resource_class):
        try:
            return cls.registered_resources[resource_class]
        except KeyError:
            raise ResourceNotRegisteredError('Resource %s is not registered for cost tracking. Make sure that its '
                                             'strategy is added to CostTrackingRegister' % resource_class.__name__)

    @classmethod
    def get_configuration(cls, resource):
        """ Return how much consumables are used by resource with current configuration.

            Output example:
            {
                <ConsumableItem instance>: <usage>,
                <ConsumableItem instance>: <usage>,
                ...
            }
        """
        strategy = cls._get_strategy(resource.__class__)
        return strategy.get_configuration(resource)

    @classmethod
    def get_consumable_items(cls, resource_class):
        """ Get all possible consumable items for given resource class """
        strategy = cls._get_strategy(resource_class)
        return strategy.get_consumable_items()

    # XXX: deprecated. Should be removed.
    @classmethod
    def register(cls, app_label, backend):
        cls._register[app_label] = backend

    # XXX: deprecated. Should be removed.
    @classmethod
    def get_registered_backends(cls):
        return cls._register.values()

    # XXX: deprecated. Should be removed.
    @classmethod
    def get_resource_backend(cls, resource):
        try:
            return cls._register[resource._meta.app_label]
        except KeyError:
            raise ServiceBackendNotImplemented


# XXX: This backend should be removed
class CostTrackingBackend(object):
    """ Cost tracking interface for NC plugin """

    # A list of numerical <item type>'s like storage or users count
    NUMERICAL = []

    # Should be used as consistent name for different VM types
    VM_SIZE_ITEM_TYPE = 'flavor'  # WTF?

    @classmethod
    def get_used_items(cls, resource):
        """ Return list of items that are currently used by resource

        Return format: [(<item type>, <item name>, <item usage>), ...]
        <item usage> should be 1 for all uncountable items (flavors, installed OS ...)
        """
        raise NotImplementedError()

    @classmethod
    def get_service_price_list_items(cls, service):
        """ Return list of price items for concrete service """
        raise NotImplementedError()

    @classmethod
    def get_default_price_list_items(cls):
        """ Return list of default price items for application """
        raise NotImplementedError()

    @classmethod
    def get_monthly_cost_estimate(cls, resource):
        """ Get resource monthly cost estimate.

        By default monthly cost estimate is calculated as multiplication
        of default price list items prices on used items time.
        Cost estimate is calculated using price list of resource's service if possible.

        Method should return decimal as result.
        """
        price_map = cls._get_price_map(resource)

        monthly_cost = 0
        for item_type, item_key, item_count in cls.get_used_items(resource):
            key = (item_type, item_key)
            value = price_map.get(key)
            if value is None:
                logger.error('Can not find price item with key "%s" and type "%s" for resource "%s"',
                             item_key, item_type, resource)
            else:
                monthly_cost += value * Decimal(format(item_count, ".15g"))
        return monthly_cost

    @classmethod
    def _get_price_map(cls, resource):
        """
        Return mapping from (item_type, key) to monthly_rate.
        If service-specific price list item is unavailable, default
        price list item is used instead for fetching monthly_rate.
        """
        from django.contrib.contenttypes.models import ContentType
        from nodeconductor.cost_tracking.models import DefaultPriceListItem, PriceListItem
        resource_content_type = ContentType.objects.get_for_model(resource)

        price_list_items = PriceListItem.objects.filter(service=resource.service_project_link.service)
        prefetch = Prefetch('pricelistitem_set', queryset=price_list_items, to_attr='service_item')

        price_items = DefaultPriceListItem.objects\
            .filter(resource_content_type=resource_content_type)\
            .prefetch_related(prefetch)

        price_map = {}
        for item in price_items:
            key = (item.item_type, item.key)
            val = item.monthly_rate
            if item.service_item:
                # service_item list either contains one element or empty
                val = item.service_item[0].monthly_rate
            price_map[key] = Decimal(val)
        return price_map
