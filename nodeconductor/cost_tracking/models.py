from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.lru_cache import lru_cache
from jsonfield import JSONField
from model_utils import FieldTracker

from nodeconductor.core import models as core_models
from nodeconductor.cost_tracking import managers, CostConstants
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
            [structure_models.Project, structure_models.Customer]
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

    key = models.CharField(max_length=50)
    value = models.DecimalField(default=0, max_digits=16, decimal_places=8)
    units = models.CharField(max_length=30, blank=True)
    item_type = models.CharField(max_length=30,
                                 choices=CostConstants.PriceItem.CHOICES,
                                 default=CostConstants.PriceItem.FLAVOR)


class DefaultPriceListItem(core_models.UuidMixin, AbstractPriceListItem):
    """ Default price list item for all resources of supported service types """
    resource_content_type = models.ForeignKey(ContentType)

    backend_product_id = models.CharField(max_length=255, blank=True)
    backend_option_id = models.CharField(max_length=255, blank=True)
    backend_choice_id = models.CharField(max_length=255, blank=True)

    tracker = FieldTracker()

    @classmethod
    def get_options(cls, **queryset_args):
        """ Return a dictionary with backend IDs of configurable options
            for specific product defined by resource_content_type or backend_product_id
        """
        options = {}
        for item in cls.objects.filter(**queryset_args):
            options.setdefault(item.item_type, {})
            options[item.item_type]['id'] = item.backend_option_id

            if item.backend_choice_id:
                options[item.item_type].setdefault('choices', {})
                options[item.item_type]['choices'][item.key] = item.backend_choice_id

        return options


class PriceListItem(core_models.UuidMixin, AbstractPriceListItem):
    # Generic key to service
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    service = GenericForeignKey('content_type', 'object_id')
    resource_content_type = models.ForeignKey(ContentType, related_name='+')

    is_manually_input = models.BooleanField(default=False)

    objects = managers.PriceListItemManager('service')

    class Meta:
        unique_together = ('key', 'content_type', 'object_id')


class PaidResource(models.Model):
    """ Extend Resource model with methods to track usage cost and handle orders """

    class Meta(object):
        abstract = True

    class Order(object):
        def __init__(self, instance):
            self.instance = instance

        @property
        def id(self):
            return self.instance.billing_backend_id

        @id.setter
        def id(self, val):
            try:
                self.instance.billing_backend_id = val
                self.instance.save(update_fields=['billing_backend_id'])
            except self.instance.DoesNotExist:
                pass

        @property
        def backend(self):
            return self.instance.service_project_link.service.customer.get_billing_backend()

        def _propagate_default_options(self, options):
            try:
                defaults = self.instance.get_default_price_options()
            except NotImplementedError:
                pass
            else:
                for opt in options:
                    if options[opt] in (None, '') and opt in defaults:
                        options[opt] = defaults[opt]

            return options

        def add(self):
            options = self.instance.get_price_options()
            options = self._propagate_default_options(options)
            resource_content_type = ContentType.objects.get_for_model(self.instance)
            self.id = self.backend.add_order(resource_content_type, **options)

        def update(self, **options):
            options = self._propagate_default_options(options)
            self.id = self.backend.update_order(self.id, **options)

        def accept(self):
            self.backend.accept_order(self.id)

        def cancel(self):
            self.backend.cancel_order(self.id)

        def delete(self):
            if self.id:
                self.backend.delete_order(self.id)
                self.id = ''

    billing_backend_id = models.CharField(max_length=255, blank=True)

    def get_default_price_options(self):
        raise NotImplementedError

    def get_price_options(self):
        raise NotImplementedError

    def __init__(self, *args, **kwargs):
        super(PaidResource, self).__init__(*args, **kwargs)
        self.order = self.Order(self)
