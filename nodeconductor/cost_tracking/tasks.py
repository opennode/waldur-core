import logging
import datetime

from celery import shared_task
from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from nodeconductor.cost_tracking import CostConstants
from nodeconductor.cost_tracking.models import DefaultPriceListItem, PriceEstimate
from nodeconductor.billing.models import PaidResource
from nodeconductor.structure.models import Resource
from nodeconductor.structure import ServiceBackendError, ServiceBackendNotImplemented


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.cost_tracking.update_current_month_projected_estimate')
def update_current_month_projected_estimate(customer_uuid=None, resource_uuid=None):

    if customer_uuid and resource_uuid:
        raise RuntimeError("Either customer_uuid or resource_uuid could be supplied, both received.")

    def update_price_for_scope(scope, cost):
        today = datetime.date.today()
        estimate, _ = PriceEstimate.objects.get_or_create(
            content_type=ContentType.objects.get_for_model(scope),
            object_id=scope.id,
            month=today.month,
            year=today.year)

        delta = cost - estimate.total
        if delta:
            estimate.total = cost
            estimate.save(update_fields=['total'])

        return delta

    for model in Resource.get_all_models():
        # XXX: customer filter must be applied in a first turn (NC-777)
        if customer_uuid:
            queryset = model.objects.filter(customer__uuid=customer_uuid)
        elif resource_uuid:
            queryset = model.objects.filter(uuid=resource_uuid)

        queryset = queryset.exclude(state=model.States.ERRED)
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

                # save monthly cost as is for initial scope
                delta_cost = update_price_for_scope(instance, monthly_cost)

                # increment total cost by delta for parent nodes
                spl = instance.service_project_link
                for scope in (spl, spl.project, spl.service, instance.customer):
                    update_price_for_scope(scope, monthly_cost + delta_cost)


@shared_task(name='nodeconductor.cost_tracking.update_today_usage')
def update_today_usage():
    # this task is supposed to be called every hour and count hourly resource usage
    # it's exact amount for numerical options and boolean value for the rest
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
            for r in resource.objects.all():
                update_today_usage_of_resource.delay(r.to_string())


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
