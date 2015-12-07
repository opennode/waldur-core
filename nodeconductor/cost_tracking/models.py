import logging

from dateutil.relativedelta import relativedelta
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.utils.lru_cache import lru_cache
from jsonfield import JSONField
from model_utils import FieldTracker

from nodeconductor.core import models as core_models
from nodeconductor.core.utils import hours_in_month
from nodeconductor.cost_tracking import CostTrackingRegister, managers
from nodeconductor.structure import models as structure_models
from nodeconductor.structure import ServiceBackendError, ServiceBackendNotImplemented


logger = logging.getLogger(__name__)


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
    def get_estimated_models(cls):
        return (
            structure_models.Resource.get_all_models() +
            structure_models.ServiceProjectLink.get_all_models() +
            structure_models.Service.get_all_models() +
            [structure_models.Project, structure_models.Customer]
        )

    @classmethod
    @lru_cache(maxsize=1)
    def get_editable_estimated_models(cls):
        return (
            structure_models.Resource.get_all_models() +
            structure_models.ServiceProjectLink.get_all_models()
        )

    @classmethod
    @transaction.atomic
    def update_price_for_scope(cls, scope, month, year, total, update_if_exists=True):
        estimate, created = cls.objects.get_or_create(
            content_type=ContentType.objects.get_for_model(scope),
            object_id=scope.id,
            month=month,
            year=year,
            is_manually_input=False)

        if update_if_exists or created:
            delta = total - estimate.total
            estimate.total = total
            estimate.save(update_fields=['total'])
        else:
            delta = 0

        if isinstance(scope, core_models.DescendantMixin):
            for parent in scope.get_ancestors():
                estimate, created = cls.objects.get_or_create(
                    content_type=ContentType.objects.get_for_model(parent),
                    object_id=parent.id,
                    month=month,
                    year=year,
                    is_manually_input=False)

                if delta or created:
                    estimate.total += delta
                    estimate.save(update_fields=['total'])

    @classmethod
    def update_price_for_resource(cls, resource, delete=False):
        # Do not remove estimates for resource created by NodeConductor
        if delete and not resource.imported:
            return

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

            month_start = created.replace(day=1, hour=0, minute=0, second=0)
            month_end = month_start.replace(month=month_start.month + 1)
            seconds_in_month = (month_end - month_start).total_seconds()
            seconds_of_work = (month_end - created).total_seconds()

            creation_month_cost = round(monthly_cost * seconds_of_work / seconds_in_month, 2)

            if delete:
                monthly_cost *= -1
                creation_month_cost *= -1

            if created.month == now.month and created.year == now.year:
                # update only current month estimate
                PriceEstimate.update_price_for_scope(resource, now.month, now.year, creation_month_cost)
            else:
                # update current month estimate
                PriceEstimate.update_price_for_scope(resource, now.month, now.year, monthly_cost)
                # update first month estimate
                PriceEstimate.update_price_for_scope(resource, created.month, created.year, creation_month_cost,
                                                     update_if_exists=False)
                # update price estimate for previous months if it does not exist:
                date = now - relativedelta(months=+1)
                while not (date.month == created.month and date.year == created.year):
                    PriceEstimate.update_price_for_scope(resource, date.month, date.year, monthly_cost,
                                                         update_if_exists=False)
                    date -= relativedelta(months=+1)

    def __str__(self):
        return '%s for %s-%s' % (self.scope, self.year, self.month)


class AbstractPriceListItem(models.Model):
    class Meta:
        abstract = True

    key = models.CharField(max_length=255)
    value = models.DecimalField("Hourly rate", default=0, max_digits=9, decimal_places=2)
    units = models.CharField(max_length=255, blank=True)
    item_type = models.CharField(max_length=255)

    @property
    def monthly_rate(self):
        return '%0.2f' % (self.value * hours_in_month())


class DefaultPriceListItem(core_models.UuidMixin, core_models.NameMixin, AbstractPriceListItem):
    """ Default price list item for all resources of supported service types """
    resource_content_type = models.ForeignKey(ContentType, default=None)

    tracker = FieldTracker()


class PriceListItem(core_models.UuidMixin, AbstractPriceListItem):
    # Generic key to service
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    service = GenericForeignKey('content_type', 'object_id')
    resource_content_type = models.ForeignKey(ContentType, related_name='+', default=None)

    is_manually_input = models.BooleanField(default=False)

    objects = managers.PriceListItemManager('service')

    class Meta:
        unique_together = ('key', 'content_type', 'object_id')


# XXX: this model has to be moved to OpenStack application
@python_2_unicode_compatible
class ApplicationType(core_models.NameMixin, models.Model):
    slug = models.CharField(max_length=150, unique=True)

    def __str__(self):
        return self.name
