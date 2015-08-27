import logging
import datetime

from celery import shared_task
from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from nodeconductor.cost_tracking import CostConstants, get_cost_tracking_models
from nodeconductor.cost_tracking.models import DefaultPriceListItem, PriceEstimate
from nodeconductor.billing.models import PaidResource
from nodeconductor.structure.models import Customer, Project, Resource, Service


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.cost_tracking.update_current_month_projected_estimate')
def update_current_month_projected_estimate(customer_uuid=None):
    customer = Customer.objects.get(uuid=customer_uuid) if customer_uuid else None

    def update_price_for_scope(scope, cost):
        today = datetime.date.today()
        estimate, _ = PriceEstimate.objects.get_or_create(
            content_type=ContentType.objects.get_for_model(scope),
            object_id=scope.id,
            month=today.month,
            year=today.year)

        delta = cost - estimate.total

        estimate.total = cost
        estimate.save(update_fields=['total'])

        return delta

    def get_parent_models(cls, obj):
        if isinstance(obj, Resource):
            spl = obj.service_project_link
            return spl.project, spl.service, obj.customer

        elif isinstance(obj, (Service, Project)):
            return obj.customer,

        else:
            return tuple()

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

            # save monthly cost as is for initial scope
            # XXX: only Resource should be used for initial scope if possible
            #      otherwise it's easy to break consistency of total sums
            delta = update_price_for_scope(model, cost)

            # increment total cost by delta for parent nodes if any
            for scope in get_parent_models(model):
                update_price_for_scope(scope, cost + delta)

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

    nc_settings = getattr(settings, 'NODECONDUCTOR', {})
    if not nc_settings.get('ENABLE_ORDER_PROCESSING'):
        return

    for resource in Resource.get_all_models():
        if issubclass(resource, PaidResource):
            update_today_usage_of_resource.delay(resource.to_string())


@shared_task
def update_today_usage_of_resource(resource_str):
    resource = next(Resource.from_string(resource_str))
    usage_state = resource.get_usage_state()

    numerical = CostConstants.PriceItem.NUMERICS
    content_type = ContentType.objects.get_for_model(resource)

    units = {
        (item.item_type, None if item.item_type in numerical else item.key): item.units
        for item in DefaultPriceListItem.objects.filter(resource_content_type=content_type)}

    usage = {}
    for key, val in usage_state.items():
        if val:
            usage[units[key, None if key in numerical else val]] = val if key in numerical else 1

    resource.order.add_usage(usage)
