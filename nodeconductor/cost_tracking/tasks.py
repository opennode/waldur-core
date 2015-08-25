import logging
import datetime

from celery import shared_task
from django.contrib.contenttypes.models import ContentType
from django.db.models import F

from nodeconductor.cost_tracking import CostConstants, get_cost_tracking_models
from nodeconductor.cost_tracking.models import DefaultPriceListItem, PriceEstimate, ResourceUsage
from nodeconductor.structure.models import Customer, Resource
from nodeconductor.structure import SupportedServices


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.cost_tracking.update_current_month_projected_estimate')
def update_current_month_projected_estimate(customer_uuid=None):
    dt = datetime.datetime.now()
    customer = Customer.objects.get(uuid=customer_uuid) if customer_uuid else None

    finished_items = {}
    for strategy in get_cost_tracking_models():
        for model, cost in strategy.get_all_costs_estimates(customer):
            if model.__class__ not in PriceEstimate.get_estimated_models():
                logger.error(
                    "Model %s can't be used in tracking costs" % model.__class__.__name__)
                continue

            if model in finished_items:
                logger.warn(
                    "Model %s appears second time during tracking costs. "
                    "Consider optimizing it if it's still valid behavior." % model.__class__.__name__)

            for scope in SupportedServices.get_parent_models(model):
                args = dict(
                    content_type=ContentType.objects.get_for_model(scope),
                    object_id=scope.id,
                    month=dt.month,
                    year=dt.year)

                try:
                    estimate = PriceEstimate.objects.get(**args)
                except PriceEstimate.DoesNotExist:
                    PriceEstimate.objects.create(total=cost, **args)
                else:
                    estimate.total = cost
                    estimate.save(update_fields=['total'])

            finished_items[model] = cost


@shared_task(name='nodeconductor.cost_tracking.update_today_usage')
def update_today_usage():
    # this task is suppossed to be called every hour and count hourly resource usage
    # it's exact ammount for numerical options and boolean value for the rest
    # example:
    #       2015-08-20 13:00    storage-1Gb         20
    #       2015-08-20 13:00    flavor-g1.small1    1
    #       2015-08-20 13:00    license-os-centos7  1
    #       2015-08-20 13:00    support-basic       1

    from nodeconductor.billing.models import PaidResource

    for resource in Resource.get_all_models():
        if issubclass(resource, PaidResource):
            update_today_usage_of_resource.delay(resource.to_string())


@shared_task
def update_today_usage_of_resource(resource_str):
    resource = next(Resource.from_string(resource_str))
    usage_state = resource.get_usage_state()

    numerical = (CostConstants.PriceItem.STORAGE,)
    content_type = ContentType.objects.get_for_model(resource)

    units = {
        (item.item_type, None if item.item_type in numerical else item.key): item.units
        for item in DefaultPriceListItem.objects.filter(resource_content_type=content_type)}

    today = datetime.datetime.utcnow().date()
    for key, val in usage_state.items():
        if not val:
            continue

        usage, _ = ResourceUsage.objects.get_or_create(
            date=today,
            content_type=content_type,
            object_id=resource.id,
            units=units[key, None if key in numerical else val])

        usage.value = F('value') + (val if key in numerical else 1)
        usage.save(update_fields=['value'])
