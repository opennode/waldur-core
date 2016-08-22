from celery import shared_task
from django.db.models import Sum

from nodeconductor.cost_tracking import CostTrackingRegister, models
from nodeconductor.structure import models as structure_models


@shared_task
def recalculate_consumed_estimate():
    """ Recalculate how many consumables were used by resource until now. """
    # Step 1. Recalculate resources estimates.
    for resource_model in CostTrackingRegister.registered_resources:
        for resource in resource_model.objects.all():
            price_estimate, created = models.PriceEstimate.objects.get_or_create_current_with_ancestors(scope=resource)
            if created:
                price_estimate.update_total()
            price_estimate.update_consumed()
    # Step 2. Move from down to top and recalculate consumed estimate for each
    #         objects based on its children.
    estimated_models = [structure_models.ServiceProjectLink, structure_models.Service, structure_models.Service,
                        structure_models.Project, structure_models.Customer, structure_models.ServiceSettings]
    for model in estimated_models:
        for obj in model.objects.all():
            obj.consumed = obj.children.all().aggregate(Sum('consumed'))
            obj.save(update_fields=['consumed'])
