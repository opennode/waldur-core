import logging
from dateutil.relativedelta import relativedelta

from celery import shared_task
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from nodeconductor.billing.models import PaidResource
from nodeconductor.cost_tracking import CostConstants
from nodeconductor.cost_tracking.models import DefaultPriceListItem, PriceEstimate
from nodeconductor.structure.models import Resource
from nodeconductor.structure import ServiceBackendError, ServiceBackendNotImplemented


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.cost_tracking.update_projected_estimate')
def update_projected_estimate(customer_uuid=None, resource_uuid=None):

    if customer_uuid and resource_uuid:
        raise RuntimeError("Either customer_uuid or resource_uuid could be supplied, both received.")

    def get_resource_creation_month_cost(resource, monthly_cost):
        month_start = resource.created.replace(day=1, hour=0, minute=0, second=0)
        month_end = month_start.replace(month=month_start.month+1)
        seconds_in_month = (month_end - month_start).total_seconds()
        seconds_of_work = (month_end - resource.created).total_seconds()
        return round(monthly_cost * seconds_of_work / seconds_in_month, 2)

    for model in Resource.get_all_models():
        queryset = model.objects.exclude(state=model.States.ERRED)
        if customer_uuid:
            queryset = queryset.filter(customer__uuid=customer_uuid)
        elif resource_uuid:
            queryset = queryset.filter(uuid=resource_uuid)

        for instance in queryset.iterator():
            try:
                backend = instance.get_backend()
                monthly_cost = backend.get_monthly_cost_estimate(instance)
            except ServiceBackendNotImplemented:
                continue
            except ServiceBackendError as e:
                logger.error("Failed to get cost estimate for resource %s: %s", instance, e)
            except Exception as e:
                logger.exception("Failed to get cost estimate for resource %s: %s", instance, e)
            else:
                logger.info("Update cost estimate for resource %s: %s", instance, monthly_cost)

                creation_month_cost = get_resource_creation_month_cost(instance, monthly_cost)

                now = timezone.now()
                created = instance.created
                if created.month == now.month and created.year == now.year:
                    # update only current month estimate
                    PriceEstimate.update_price_for_scope(instance, now.month, now.year, creation_month_cost)
                else:
                    # update current month estimate
                    PriceEstimate.update_price_for_scope(instance, now.month, now.year, monthly_cost)
                    # update first month estimate
                    PriceEstimate.update_price_for_scope(instance, created.month, created.year, creation_month_cost,
                                                         update_if_exists=False)
                    # update price estimate for previous months if it does not exist:
                    date = now - relativedelta(months=+1)
                    while not (date.month == created.month and date.year == created.year):
                        PriceEstimate.update_price_for_scope(instance, date.month, date.year, monthly_cost,
                                                             update_if_exists=False)
                        date -= relativedelta(months=+1)


@shared_task(name='nodeconductor.cost_tracking.update_today_usage')
def update_today_usage():
    """
    Calculate usage for all paid resources.

    Task counts exact usage amount for numerical options and boolean value for the rest.
    Example:
        2015-08-20 13:00    storage-1Gb         20
        2015-08-20 13:00    flavor-g1.small1    1
        2015-08-20 13:00    license-os-centos7  1
        2015-08-20 13:00    support-basic       1
    """

    nc_settings = getattr(settings, 'NODECONDUCTOR', {})
    if not nc_settings.get('ENABLE_ORDER_PROCESSING'):
        return

    for model in PaidResource.get_all_models():
        for resource in model.objects.all():
            update_today_usage_of_resource.delay(resource.to_string())


@shared_task
def update_today_usage_of_resource(resource_str):
    # XXX: this method does ignores cases then VM was offline or online for small periods of time.
    # It could to be rewritten if more accurate calculation will be needed
    with transaction.atomic():
        resource = next(Resource.from_string(resource_str))
        usage_state = resource.get_usage_state()

        numerical = CostConstants.PriceItem.NUMERICS
        content_type = ContentType.objects.get_for_model(resource)

        units = {
            (item.item_type, None if item.item_type in numerical else item.key): item.units
            for item in DefaultPriceListItem.objects.filter(resource_content_type=content_type)}

        now = timezone.now()
        last_update_time = resource.last_usage_update_time or resource.created
        minutes_from_last_usage_update = (now - last_update_time).total_seconds() / 60

        usage = {}
        for key, val in usage_state.items():
            if val:
                try:
                    unit = units[key, None if key in numerical else val]
                    usage_per_hour = val if key in numerical else 1
                    usage_per_min = int(round(usage_per_hour * minutes_from_last_usage_update))
                    if usage_per_min:
                        usage[unit] = usage_per_min
                except KeyError:
                    logger.error("Can't find price for usage item %s:%s", key, val)

        resource.order.add_usage(usage)
        resource.last_usage_update_time = timezone.now()
        resource.save(update_fields=['last_usage_update_time'])
