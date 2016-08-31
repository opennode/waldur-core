from __future__ import unicode_literals

import calendar
import datetime
import logging

from django.apps import apps
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.utils.lru_cache import lru_cache

from jsonfield import JSONField
from model_utils import FieldTracker
from model_utils.models import TimeStampedModel

from nodeconductor.core import models as core_models
from nodeconductor.core.utils import hours_in_month
from nodeconductor.cost_tracking import managers, ConsumableItem
from nodeconductor.logging.loggers import LoggableMixin
from nodeconductor.logging.models import AlertThresholdMixin
from nodeconductor.structure import models as structure_models, SupportedServices


logger = logging.getLogger(__name__)


class EstimateUpdateError(Exception):
    pass


@python_2_unicode_compatible
class PriceEstimate(LoggableMixin, AlertThresholdMixin, core_models.UuidMixin, core_models.DescendantMixin):
    """ Store prices based on both estimates and actual consumption.

        Every record holds a list of children estimates.
                   /--- Service ---\
        Customer --                 ---> SPL --> Resource
                   \--- Project ---/
        Only resource node has actual data.
        Another ones should be re-calculated on every change of resource estimate.
    """
    content_type = models.ForeignKey(ContentType, null=True, related_name='+')
    object_id = models.PositiveIntegerField(null=True)
    scope = GenericForeignKey('content_type', 'object_id')
    details = JSONField(default={}, help_text='Saved scope details. Field is populated on scope deletion.')
    parents = models.ManyToManyField('PriceEstimate', related_name='children', help_text='Price estimate parents')

    total = models.FloatField(default=0, help_text='Predicted price for scope for current month.')
    consumed = models.FloatField(default=0, help_text='Price for resource until now.')
    limit = models.FloatField(
        default=-1, help_text='How many funds object can consume in current month."-1" means no limit.')

    month = models.PositiveSmallIntegerField(validators=[MaxValueValidator(12), MinValueValidator(1)])
    year = models.PositiveSmallIntegerField()

    objects = managers.PriceEstimateManager('scope')

    class Meta:
        unique_together = ('content_type', 'object_id', 'month', 'year',)

    def __str__(self):
        name = self._get_scope_name() if self.scope else self.details.get('name')
        return '%s for %s-%s %.2f' % (name, self.year, self.month, self.total)

    @classmethod
    @lru_cache(maxsize=1)
    def get_estimated_models(cls):
        return (
            structure_models.ResourceMixin.get_all_models() +
            structure_models.ServiceProjectLink.get_all_models() +
            structure_models.Service.get_all_models() +
            [structure_models.ServiceSettings] +
            [structure_models.Project, structure_models.Customer]
        )

    def get_parents(self):  # For DescendantMixin
        return self.parents.all()

    def get_children(self):  # For DescendantMixin
        return self.children.all()

    def get_log_fields(self):  # For LoggableMixin
        return 'uuid', 'scope', 'threshold', 'total', 'consumed'

    def is_over_threshold(self):  # For AlertThresholdMixin
        return self.total > self.threshold

    @classmethod
    def get_checkable_objects(cls):  # For AlertThresholdMixin
        """ Raise alerts only for price estimates that describes current month. """
        today = timezone.now()
        return cls.objects.filter(year=today.year, month=today.month)

    def get_previous(self):
        """ Get estimate for the same scope for previous month. """
        month, year = (self.month - 1, self.year) if self.month != 1 else (12, self.year - 1)
        return PriceEstimate.objects.get(scope=self.scope, month=month, year=year)

    def create_ancestors(self):
        """ Crete price estimates for scope ancestors if they does not exists """
        if not isinstance(self.scope, core_models.DescendantMixin):
            return
        scope_parents = self.scope.get_parents()
        for scope_parent in scope_parents:
            parent, created = PriceEstimate.objects.get_or_create(scope=scope_parent, month=self.month, year=self.year)
            self.parents.add(parent)
            if created:
                parent.create_ancestors()

    def init_details(self):
        """ Initialize price estimate details based on its scope """
        self.details = {
            'name': self._get_scope_name(),
            'description': getattr(self.scope, 'description', ''),
        }
        if hasattr(self.scope, 'backend_id'):
            self.details['backend_id'] = self.scope.backend_id
        self.save(update_fields=['details'])

    def update_total(self, update_ancestors=True):
        """ Re-calculate price of resource and its ancestors for whole month,
            based on its configuration and consumption details.
        """
        self._check_is_updatable()
        new_total = self._get_price(self.consumption_details.consumed_in_month)
        diff = new_total - self.total
        with transaction.atomic():
            self.total = new_total
            self.save(update_fields=['total'])
            if update_ancestors:
                self.update_ancestors_total(diff)

    def update_ancestors_total(self, diff):
        for ancestor in self.get_ancestors():
            ancestor.total += diff
            ancestor.save(update_fields=['total'])

    def update_consumed(self):
        """ Re-calculate price of resource until now. Does not update ancestors. """
        self._check_is_updatable()
        self.consumed = self._get_price(self.consumption_details.consumed_until_now)
        self.save(update_fields=['consumed'])

    def _get_price(self, consumed):
        """ Calculate price estimate for scope depends on consumed data and price list items.
            Map each consumable to price list item and multiply price its price by time of usage.
        """
        price_list_items = PriceListItem.get_for_resource(self.scope)
        consumables_prices = {(item.item_type, item.key): item.minute_rate for item in price_list_items}
        total = 0
        for consumable_item, usage in consumed.items():
            try:
                total += consumables_prices[(consumable_item.item_type, consumable_item.key)] * usage
            except KeyError:
                logger.error('Price list item for consumable "%s" does not exist.' % consumable_item)
        return total

    def _check_is_updatable(self):
        """ Raise error if price estimate does not have consumption details or
            does not belong to resource
        """
        if self.consumption_details is None:
            raise EstimateUpdateError('Cannot update consumed for price estimate that does not have consumption details.')
        if not isinstance(self.scope, structure_models.ResourceMixin):
            raise EstimateUpdateError('Cannot update consumed for price estimate that is not related to resource.')

    def _get_scope_name(self):
        if isinstance(self.scope, structure_models.ServiceProjectLink):
            # We need to display some meaningful name for SPL.
            return str(self.scope)
        else:
            return self.scope.name


class ConsumptionDetailUpdateError(Exception):
    pass


class ConsumptionDetailCalculateError(Exception):
    pass


class ConsumableItemsField(JSONField):
    """ Store consumable items and their usage as JSON.

        Represent data in format:
        {
            <ConsumableItem instance>: <usage>,
            <ConsumableItem instance>: <usage>,
            ...
        }
        Store data in format:
        [
            {
                "item_type": xx,
                "key": xx,
                "usage": xx,
            }
            ...
        ]
    """
    def pre_init(self, value, obj):
        """ JSON field initializes field in "pre_init" method, so it is better to override it. """
        value = super(ConsumableItemsField, self).pre_init(value, obj)
        if obj._state.adding:
            value = self._deserialize(value)
        return value

    def get_db_prep_value(self, value, connection, prepared=False):
        if prepared:
            return value

        if not isinstance(value, dict):
            raise TypeError('ConsumableItemsField value should be dict. Received: %s' % value)
        if any([not isinstance(item, ConsumableItem) for item in value]):
            raise TypeError('ConsumableItemsField keys should be instances of ConsumableItem class.')

        prep_value = self._serialize(value)
        return super(ConsumableItemsField, self).get_db_prep_value(prep_value, connection, prepared)

    def _serialize(self, value):
        return [{'usage': usage, 'item_type': item.item_type, 'key': item.key}
                for item, usage in value.items()]

    def _deserialize(self, serialized_value):
        return {ConsumableItem(item['item_type'], item['key']): item['usage'] for item in serialized_value}


class ConsumptionDetails(core_models.UuidMixin, TimeStampedModel):
    """ Resource consumption details per month.

        Warning! Use method "update_configuration" to update configurations,
        do not update them manually.
    """
    price_estimate = models.OneToOneField(PriceEstimate, related_name='consumption_details')
    configuration = ConsumableItemsField(default={}, help_text='Current resource configuration.')
    last_update_time = models.DateTimeField(help_text='Last configuration change time.')
    consumed_before_update = ConsumableItemsField(
        default={}, help_text='How many consumables were used by resource before last update.')

    objects = managers.ConsumptionDetailsManager()

    def update_configuration(self, new_configuration):
        """ Save how much consumables were used and update current configuration. """
        if new_configuration == self.configuration:
            return
        now = timezone.now()
        if now.month != self.price_estimate.month:
            raise ConsumptionDetailUpdateError('It is possible to update consumption details only for current month.')
        minutes_from_last_update = self._get_minutes_from_last_update(now)
        for consumable_item, usage in self.configuration.items():
            consumed_after_modification = usage * minutes_from_last_update
            self.consumed_before_update[consumable_item] = (
                self.consumed_before_update.get(consumable_item, 0) + consumed_after_modification)
        self.configuration = new_configuration
        self.last_update_time = now
        self.save()

    @property
    def consumed_in_month(self):
        """ How many resources were (or will be) consumed until end of the month """
        return self._get_consumed(self._get_month_end())

    @property
    def consumed_until_now(self):
        """ How many consumables were used by resource until now. """
        return self._get_consumed(timezone.now())

    def _get_consumed(self, time):
        """ How many consumables were used (or will be) by resource until given time. """
        minutes_from_last_update = self._get_minutes_from_last_update(time)
        if minutes_from_last_update < 0:
            raise ConsumptionDetailCalculateError('Cannot calculate consumption if time < last modification date.')
        _consumed = {}
        for consumable_item in set(self.configuration.keys() + self.consumed_before_update.keys()):
            after_update = self.configuration.get(consumable_item, 0) * minutes_from_last_update
            before_update = self.consumed_before_update.get(consumable_item, 0)
            _consumed[consumable_item] = after_update + before_update
        return _consumed

    def _get_month_end(self):
        year, month = self.price_estimate.year, self.price_estimate.month
        days_in_month = calendar.monthrange(year, month)[1]
        last_day_of_month = datetime.date(month=month, year=year, day=days_in_month)
        last_second_of_month = datetime.datetime.combine(last_day_of_month, datetime.time.max)
        return timezone.make_aware(last_second_of_month, timezone.get_current_timezone())

    def _get_minutes_from_last_update(self, time):
        """ How much minutes passed from last update to given time """
        time_from_last_update = time - self.last_update_time
        return int(time_from_last_update.total_seconds() / 60)


class AbstractPriceListItem(models.Model):
    class Meta:
        abstract = True

    value = models.DecimalField("Hourly rate", default=0, max_digits=11, decimal_places=5)
    units = models.CharField(max_length=255, blank=True)

    @property
    def monthly_rate(self):
        return '%0.2f' % (self.value * 60 * hours_in_month())

    @property
    def minute_rate(self):
        return float(self.value) / 60


@python_2_unicode_compatible
class DefaultPriceListItem(core_models.UuidMixin, core_models.NameMixin, AbstractPriceListItem):
    """
    Default price list item for all resources of supported service types.

    It is fetched from cost tracking backend.
    Field "name" represents how price item will be represented for user.
    """
    item_type = models.CharField(max_length=255, help_text='Type of price list item. Examples: storage, flavor.')
    key = models.CharField(
        max_length=255, help_text='Key that corresponds particular consumable. Example: name of flavor.')
    resource_content_type = models.ForeignKey(ContentType, default=None)
    # Field "metadata" is deprecated. We decided to store objects separately from their prices.
    metadata = JSONField(
        blank=True, help_text='Details of the item, that corresponds price list item. Example: details of flavor.')

    tracker = FieldTracker()

    def __str__(self):
        return 'Price list item %s: %s = %s for %s' % (self.name, self.key, self.value, self.resource_content_type)

    class Meta:
        unique_together = ('key', 'item_type', 'resource_content_type')

    @property
    def resource_type(self):
        cls = self.resource_content_type.model_class()
        if cls:
            return SupportedServices.get_name_for_model(cls)


class PriceListItem(core_models.UuidMixin, AbstractPriceListItem):
    """
    Price list item related to private service.
    It is entered manually by customer owner.
    """
    # Generic key to service
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    service = GenericForeignKey('content_type', 'object_id')
    objects = managers.PriceListItemManager('service')
    default_price_list_item = models.ForeignKey(DefaultPriceListItem)

    class Meta:
        unique_together = ('content_type', 'object_id', 'default_price_list_item')

    def clean(self):
        if SupportedServices.is_public_service(self.service):
            raise ValidationError('Public service does not support price list items')

        resource = self.default_price_list_item.resource_content_type.model_class()
        valid_resources = SupportedServices.get_related_models(self.service)['resources']

        if resource not in valid_resources:
            raise ValidationError('Service does not support required content type')

    @staticmethod
    def get_for_resource(resource):
        """ Get list of all price list items that should be used for resource.

            If price list item is defined for service - return it, otherwise -
            return default price list item.
        """
        resource_content_type = ContentType.objects.get_for_model(resource)
        default_items = set(DefaultPriceListItem.objects.filter(resource_content_type=resource_content_type))
        service = resource.service_project_link.service
        items = set(PriceListItem.objects.filter(
            default_price_list_item__in=default_items, service=service).select_related('default_price_list_item'))
        rewrited_defaults = set([i.default_price_list_item for i in items])
        return items | (default_items - rewrited_defaults)


# Deprecated. Should be removed.
class PayableMixin(models.Model):
    """ Extend Resource model with methods to track usage cost and handle orders """

    billing_backend_id = models.CharField(max_length=255, blank=True, help_text='ID of a resource in backend')
    last_usage_update_time = models.DateTimeField(blank=True, null=True)

    @classmethod
    @lru_cache(maxsize=1)
    def get_all_models(cls):
        return [model for model in apps.get_models() if issubclass(model, cls)]

    class Meta(object):
        abstract = True
