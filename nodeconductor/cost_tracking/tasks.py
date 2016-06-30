from celery import shared_task

from nodeconductor.core.utils import deserialize_instance
from nodeconductor.cost_tracking.models import PriceEstimate, PayableMixin


@shared_task(name='nodeconductor.cost_tracking.update_projected_estimate')
def update_projected_estimate(customer_uuid=None, serialized_resource=None):

    if customer_uuid and serialized_resource:
        raise RuntimeError("Either customer_uuid or serialized_resource could be supplied, both received.")

    if serialized_resource:
        resource = deserialize_instance(serialized_resource)
        PriceEstimate.update_price_for_resource(resource)

    else:
        # XXX: it's quite inefficient -- will update ancestors many times
        for model in PayableMixin.get_all_models():
            queryset = model.objects.exclude(state=model.States.ERRED)
            if customer_uuid:
                queryset = queryset.filter(customer__uuid=customer_uuid)

            for resource in queryset.iterator():
                PriceEstimate.update_price_for_resource(resource)
