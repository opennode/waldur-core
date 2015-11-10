import logging
from dateutil.relativedelta import relativedelta

from celery import shared_task
from django.utils import timezone

from nodeconductor.cost_tracking import CostTrackingRegister
from nodeconductor.cost_tracking.models import PriceEstimate
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
                cost_tracking_backend = CostTrackingRegister.get_resource_backend(instance)
                monthly_cost = cost_tracking_backend.get_monthly_cost_estimate(instance)
            except ServiceBackendNotImplemented as e:
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
