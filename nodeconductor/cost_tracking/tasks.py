from celery import shared_task

from nodeconductor.cost_tracking.models import PriceEstimate
from nodeconductor.structure.models import Resource


@shared_task(name='nodeconductor.cost_tracking.update_projected_estimate')
def update_projected_estimate(customer_uuid=None, resource_uuid=None):

    if customer_uuid and resource_uuid:
        raise RuntimeError("Either customer_uuid or resource_uuid could be supplied, both received.")

    for model in Resource.get_all_models():
        queryset = model.objects.exclude(state=model.States.ERRED)
        if customer_uuid:
            queryset = queryset.filter(customer__uuid=customer_uuid)
        elif resource_uuid:
            queryset = queryset.filter(uuid=resource_uuid)

        for instance in queryset.iterator():
            PriceEstimate.update_price_for_resource(instance)
