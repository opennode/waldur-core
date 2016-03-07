from celery import shared_task

from nodeconductor.cost_tracking.models import PriceEstimate
from nodeconductor.structure.models import Resource


@shared_task(name='nodeconductor.cost_tracking.update_projected_estimate')
def update_projected_estimate(customer_uuid=None, resource_str=None):

    if customer_uuid and resource_str:
        raise RuntimeError("Either customer_uuid or resource_str could be supplied, both received.")

    if resource_str:
        resource = next(Resource.from_string(resource_str))
        PriceEstimate.update_price_for_resource(resource)

    else:
        # XXX: it's quite inefficient -- will update ancestors many times
        for model in Resource.get_all_models():
            queryset = model.objects.exclude(state=model.States.ERRED)
            if customer_uuid:
                queryset = queryset.filter(customer__uuid=customer_uuid)

            for resource in queryset.iterator():
                PriceEstimate.update_price_for_resource(resource)
