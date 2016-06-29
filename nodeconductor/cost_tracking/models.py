from __future__ import unicode_literals

import calendar
import logging

from dateutil.relativedelta import relativedelta
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction, IntegrityError
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.utils.lru_cache import lru_cache

from jsonfield import JSONField
from model_utils import FieldTracker
from gm2m import GM2MField

from nodeconductor.core import models as core_models
from nodeconductor.core.utils import hours_in_month
from nodeconductor.cost_tracking import CostTrackingRegister, managers
from nodeconductor.logging.loggers import LoggableMixin
from nodeconductor.logging.models import AlertThresholdMixin
from nodeconductor.structure import models as structure_models
from nodeconductor.structure import SupportedServices, ServiceBackendError, ServiceBackendNotImplemented


logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class PriceEstimate(LoggableMixin, AlertThresholdMixin, core_models.UuidMixin):
    """ Store prices based on both estimates and actual consumption.
        Every record holds a list of leaf estimates with actual data.

                         /--- Service ---\
        (top) Customer --                 ---> SPL --> Resource (leaf)
                         \--- Project ---/

        Only leaf node has actual data.
        Another ones should be re-calculated on every change of leaf one.
    """

    content_type = models.ForeignKey(ContentType, null=True, related_name='+')
    object_id = models.PositiveIntegerField(null=True)
    scope = GenericForeignKey('content_type', 'object_id')

    scope_customer = models.ForeignKey(structure_models.Customer, null=True, related_name='+')
    leaf_estimates = GM2MField('PriceEstimate')

    total = models.FloatField(default=0)
    consumed = models.FloatField(default=0)
    details = JSONField(blank=True)
    limit = models.FloatField(default=-1)

    month = models.PositiveSmallIntegerField(validators=[MaxValueValidator(12), MinValueValidator(1)])
    year = models.PositiveSmallIntegerField()

    is_manually_input = models.BooleanField(default=False)
    is_visible = models.BooleanField(default=True)

    objects = managers.PriceEstimateManager('scope')

    class Meta:
        unique_together = ('content_type', 'object_id', 'month', 'year', 'is_manually_input')

    @classmethod
    @lru_cache(maxsize=1)
    def get_estimated_models(cls):
        return (
            structure_models.ResourceMixin.get_all_models() +
            structure_models.ServiceProjectLink.get_all_models() +
            structure_models.Service.get_all_models() +
            [structure_models.Project, structure_models.Customer]
        )

    @classmethod
    @lru_cache(maxsize=1)
    def get_editable_estimated_models(cls):
        return (
            structure_models.ResourceMixin.get_all_models() +
            structure_models.ServiceProjectLink.get_all_models()
        )

    @property
    def is_leaf(self):
        return self.scope and self.is_leaf_scope(self.scope)

    @staticmethod
    def is_leaf_scope(scope):
        return scope._meta.model in structure_models.ResourceMixin.get_all_models()

    def update_from_leaf(self):
        if self.is_leaf:
            return

        leaf_estimates = list(self.leaf_estimates.all())
        self.total = sum(e.total for e in leaf_estimates)
        self.consumed = sum(e.consumed for e in leaf_estimates)
        self.save(update_fields=['total', 'consumed'])

    def update_ancestors(self):
        for parent in self.scope.get_ancestors():
            parent_estimate, created = self.__class__.objects.get_or_create(
                object_id=parent.id,
                content_type=ContentType.objects.get_for_model(parent),
                month=self.month, year=self.year)
            if self.is_leaf:
                try:
                    parent_estimate.leaf_estimates.add(self)
                except IntegrityError:  # ignore duplicates
                    pass
            parent_estimate.update_from_leaf()

    @classmethod
    def update_ancestors_for_resource(cls, resource):
        for estimate in cls.objects.filter(scope=resource, is_manually_input=False):
            estimate.update_ancestors()

    @classmethod
    def delete_estimates_for_resource(cls, resource):
        for estimate in cls.objects.filter(scope=resource):
            estimate.delete()
            for parent in resource.get_ancestors():
                qs = cls.objects.filter(scope=parent, month=estimate.month, year=estimate.year)
                for parent_estimate in qs:
                    parent_estimate.leaf_estimates.remove(estimate)
                    parent_estimate.update_from_leaf()

    @classmethod
    def update_metadata_for_scope(cls, scope):
        cls.objects.filter(scope=scope).update(
            scope_customer=scope.customer,
            details=dict(
                scope_name=scope.name,
                scope_type=SupportedServices.get_name_for_model(scope),
                scope_backend_id=scope.backend_id,
            ))

    @classmethod
    def update_price_for_scope(cls, scope):
        # update Resource and re-calculate ancestors
        if cls.is_leaf_scope(scope):
            return cls.update_price_for_resource(scope)

        # re-calculate scope and descendants till Resource
        family_scope = [scope] + [s for s in scope.get_descendants() if not cls.is_leaf_scope(s)]
        for estimate in cls.objects.filter(scope__in=family_scope, is_manually_input=False):
            estimate.update_from_leaf()

    @classmethod
    def update_price_for_resource(cls, resource):

        @transaction.atomic
        def update_estimate(month, year, total, consumed=None, update_if_exists=True):
            estimate, created = cls.objects.get_or_create(
                object_id=resource.id,
                content_type=ContentType.objects.get_for_model(resource),
                month=month, year=year, is_manually_input=False)

            if update_if_exists or created:
                estimate.consumed = total if consumed is None else consumed
                estimate.total = total
                estimate.save(update_fields=['total', 'consumed'])

        try:
            cost_tracking_backend = CostTrackingRegister.get_resource_backend(resource)
            monthly_cost = float(cost_tracking_backend.get_monthly_cost_estimate(resource))
        except ServiceBackendNotImplemented:
            return
        except ServiceBackendError as e:
            logger.error("Failed to get cost estimate for resource %s: %s", resource, e)
        except Exception as e:
            logger.exception("Failed to get cost estimate for resource %s: %s", resource, e)
        else:
            logger.info("Update cost estimate for resource %s: %s", resource, monthly_cost)

            now = timezone.now()
            created = resource.created

            days_in_month = calendar.monthrange(created.year, created.month)[1]
            month_start = created.replace(day=1, hour=0, minute=0, second=0)
            month_end = month_start + timezone.timedelta(days=days_in_month)
            seconds_in_month = (month_end - month_start).total_seconds()

            def prorata_cost(work_interval):
                return round(monthly_cost * work_interval.total_seconds() / seconds_in_month, 2)

            if created.month == now.month and created.year == now.year:
                # update only current month
                update_estimate(
                    now.month, now.year,
                    total=prorata_cost(month_end - created),
                    consumed=prorata_cost(now - created))
            else:
                # update current month
                update_estimate(
                    now.month, now.year,
                    total=monthly_cost,
                    consumed=prorata_cost(now - now.replace(day=1, hour=0, minute=0, second=0)))

                # update first month
                update_estimate(
                    created.month, created.year,
                    total=prorata_cost(month_end - created),
                    update_if_exists=False)

                # update price for previous months if it does not exist:
                date = now - relativedelta(months=+1)
                while not (date.month == created.month and date.year == created.year):
                    update_estimate(date.month, date.year, monthly_cost, update_if_exists=False)
                    date -= relativedelta(months=+1)

    def get_log_fields(self):
        return 'uuid', 'scope', 'threshold', 'total', 'consumed'

    def is_over_threshold(self):
        return self.total >= self.threshold

    @classmethod
    def get_checkable_objects(cls):
        dt = timezone.now()
        return cls.objects.filter(year=dt.year, month=dt.month)

    def __str__(self):
        return '%s for %s-%s %.2f' % (self.scope, self.year, self.month, self.total)


class AbstractPriceListItem(models.Model):
    class Meta:
        abstract = True

    value = models.DecimalField("Hourly rate", default=0, max_digits=11, decimal_places=5)
    units = models.CharField(max_length=255, blank=True)  # TODO: Rename to currency

    @property
    def monthly_rate(self):
        return '%0.2f' % (self.value * hours_in_month())


@python_2_unicode_compatible
class DefaultPriceListItem(core_models.UuidMixin, core_models.NameMixin, AbstractPriceListItem):
    """
    Default price list item for all resources of supported service types.
    It is fetched from cost tracking backend.
    """
    resource_content_type = models.ForeignKey(ContentType, default=None)
    key = models.CharField(max_length=255)
    item_type = models.CharField(max_length=255)
    metadata = JSONField(blank=True)

    tracker = FieldTracker()

    def __str__(self):
        return 'Price list item %s: %s = %s for %s' % (self.name, self.key, self.value, self.resource_content_type)

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
