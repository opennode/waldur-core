import logging
import datetime

from celery import shared_task
from django.db.models import F
from django.contrib.contenttypes.models import ContentType

from nodeconductor.cost_tracking import get_cost_tracking_models
from nodeconductor.cost_tracking.models import PriceEstimate
from nodeconductor.structure.models import Customer
from nodeconductor.structure import SupportedServices


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.cost_tracking.update_current_month_projected_estimate')
def update_current_month_projected_estimate(customer_uuid=None):
    dt = datetime.datetime.now()
    customer = Customer.objects.get(uuid=customer_uuid) if customer_uuid else None

    for strategy in get_cost_tracking_models():
        for model, cost in strategy.get_costs_estimates(customer):
            if model.__class__ not in PriceEstimate.get_estimated_models():
                logger.error(
                    "Model %s can't be used in tracking costs" % model.__class__.__name__)
                continue

            for scope in SupportedServices.get_parent_models(model):
                args = dict(
                    content_type=ContentType.objects.get_for_model(scope),
                    object_id=scope.id,
                    month=dt.month,
                    year=dt.year,
                )

                try:
                    estimate = PriceEstimate.objects.get(**args)
                except PriceEstimate.DoesNotExist:
                    PriceEstimate.objects.create(total=cost, **args)
                else:
                    estimate.total = F('total') + cost
                    estimate.save(update_fields=['total'])
