from celery import shared_task

from nodeconductor.cost_tracking import CostTrackingRegister, models
from nodeconductor.structure import models as structure_models


@shared_task(name='nodeconductor.cost_tracking.recalculate_consumed_estimate')
def recalculate_consumed_estimate():
    """ Recalculate how many consumables were used by resource until now.

        Regular task. It is too expensive to calculate consumed price on each
        request, so we store cached price each hour.
    """
    # Step 1. Recalculate resources estimates.
    for resource_model in CostTrackingRegister.registered_resources:
        for resource in resource_model.objects.all():
            _update_resource_consumed(resource)
    # Step 2. Move from down to top and recalculate consumed estimate for each
    #         objects based on its children.
    ancestors_models = [m for m in models.PriceEstimate.get_estimated_models()
                        if not issubclass(m, structure_models.ResourceMixin)]
    for model in ancestors_models:
        for ancestor in model.objects.all():
            _update_ancestor_consumed(ancestor)


def _update_resource_consumed(resource):
    price_estimate, created = models.PriceEstimate.objects.get_or_create_current_with_ancestors(scope=resource)
    if created:
        models.ConsumptionDetails.objects.create(price_estimate=price_estimate)
        price_estimate.update_total()
    price_estimate.update_consumed()


def _update_ancestor_consumed(ancestor):
    price_estimate, _ = models.PriceEstimate.objects.get_or_create_current(scope=ancestor)
    resource_descendants = [descendant for descendant in price_estimate.get_descendants()
                            if isinstance(descendant.scope, structure_models.ResourceMixin)]
    price_estimate.consumed = sum([descendant.consumed for descendant in resource_descendants])
    price_estimate.save(update_fields=['consumed'])
