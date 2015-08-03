import inspect

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.lru_cache import lru_cache
from jsonfield import JSONField

from nodeconductor.core import models as core_models
from nodeconductor.cost_tracking import managers
from nodeconductor.structure import models as structure_models


class PriceEstimate(core_models.UuidMixin, models.Model):
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    scope = GenericForeignKey('content_type', 'object_id')

    total = models.FloatField(default=0)
    details = JSONField(blank=True)

    month = models.PositiveSmallIntegerField(validators=[MaxValueValidator(12), MinValueValidator(1)])
    year = models.PositiveSmallIntegerField()

    is_manually_input = models.BooleanField(default=False)
    is_visible = models.BooleanField(default=True)

    objects = managers.PriceEstimateManager('scope')

    class Meta:
        unique_together = ('content_type', 'object_id', 'month', 'year', 'is_manually_input')

    @classmethod
    @lru_cache(maxsize=1)
    def get_estimated_models(self):
        return (
            structure_models.Resource.get_all_models() +
            structure_models.ServiceProjectLink.get_all_models() +
            structure_models.Service.get_all_models() +
            [structure_models.Project]
        )

    @classmethod
    @lru_cache(maxsize=1)
    def get_editable_estimated_models(self):
        return (
            structure_models.Resource.get_all_models() +
            structure_models.ServiceProjectLink.get_all_models()
        )


class AbstractPriceListItem(models.Model):
    class Meta:
        abstract = True

    class Types(object):
        FLAVOR = 'flavor'
        STORAGE = 'storage'
        LICENSE = 'license'
        SUPPORTED = 'supported'
        OTHER = 'other'

        CHOICES = (
            (FLAVOR, 'flavor'), (STORAGE, 'storage'), (LICENSE, 'license'), (SUPPORTED, 'supported'), (OTHER, 'other')
        )

    key = models.CharField(max_length=50)
    value = models.DecimalField(default=0, max_digits=16, decimal_places=8)
    units = models.CharField(max_length=30, blank=True)
    item_type = models.CharField(max_length=10, choices=(Types.CHOICES), default=Types.OTHER)


class DefaultPriceListItem(core_models.UuidMixin, AbstractPriceListItem):
    """ Default price list item for all services of connected type """
    service_content_type = models.ForeignKey(ContentType)

    is_manually_input = models.BooleanField(default=False)


class PriceListItem(core_models.UuidMixin, AbstractPriceListItem):
    # Generic key to service. If service is null - this price item is default.
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    service = GenericForeignKey('content_type', 'object_id')

    objects = managers.PriceListItemManager('service')

    class Meta:
        unique_together = ('key', 'content_type', 'object_id')


class ResourcePriceItem(core_models.UuidMixin, models.Model):
    """ Many to many connection between Resource and PriceListItem """
    item = models.ForeignKey('PriceListItem', related_name='resource_price_items')
    # Generic key to service
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    resource = GenericForeignKey('content_type', 'object_id')

    objects = managers.ResourcePriceItemManager('resource')

    class Meta:
        unique_together = ('item', 'content_type', 'object_id')


class ServicePriceOptions(object):
    """ Abstract class for service registration options """
    def get_service_class(self):
        raise NotImplementedError()

    def get_service_keys_with_types(self):
        """ Return list of tuples (<price list item key>, <price list item type>) """
        raise NotImplementedError()


class PriceKeysRegister(object):
    services = {}

    @classmethod
    def register(cls, options):
        """
        Register new service class and create default price list items for it.

        <options> parameter has to be instance of ServicePriceOptions.
        """
        service_class = options.get_service_class()

        if service_class not in cls.services:
            cls.services[service_class] = options.get_service_keys_with_types()

    @classmethod
    def get_keys_with_types_for_service(cls, service):
        if inspect.isclass(service):
            service_class = service
        else:
            service_class = service.__class__
        return cls.services.get(service_class, [])

    @classmethod
    def get_keys_with_types_for_resource(cls, resource):
        return cls.services.get(resource.service_project_link.service.__class__, [])
