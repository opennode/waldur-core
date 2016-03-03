from celery import shared_task

from nodeconductor.cost_tracking.models import PriceEstimate
from nodeconductor.structure.models import Customer, Resource


@shared_task(name='nodeconductor.cost_tracking.update_projected_estimate')
def update_projected_estimate(customer_uuid=None, resource_str=None):

    if resource_str:
        resource = next(Resource.from_string(resource_str))
        PriceEstimate.update_price_for_scope(resource)

    elif customer_uuid:
        customer = Customer.objects.get(uuid=customer_uuid)
        PriceEstimate.update_price_for_scope(customer)

    else:
        for model in Resource.get_all_models():
            for resource in model.objects.exclude(state=model.States.ERRED):
                PriceEstimate.update_price_for_scope(resource)
