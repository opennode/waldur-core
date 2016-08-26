import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from nodeconductor.cost_tracking import models, CostTrackingRegister
from nodeconductor.structure import models as structure_models


class Command(BaseCommand):
    help = ("Delete all price estimates that are related to current month and "
            "create new ones based on current consumption.")

    def handle(self, *args, **options):
        today = timezone.now()
        with transaction.atomic():
            # Delete current month price estimates
            models.PriceEstimate.objects.filter(month=today.month, year=today.year).delete()
            # Recalculate resources estimates.
            for resource_model in CostTrackingRegister.registered_resources:
                for resource in resource_model.objects.all():
                    _create_resource_estimate(resource, today)
            # Move from down to top and recalculate consumed estimate for each
            # objects based on its children.
            ancestors_models = [m for m in models.PriceEstimate.get_estimated_models()
                                if not issubclass(m, structure_models.ResourceMixin)]
            for model in ancestors_models:
                for ancestor in model.objects.all():
                    _update_ancestor_consumed(ancestor, today)


def _get_month_start(today):
    return timezone.make_aware(datetime.datetime(day=1, month=today.month, year=today.year))


def _create_resource_estimate(resource, today):
    price_estimate = models.PriceEstimate.objects.create(scope=resource, month=today.month, year=today.year)
    details = models.ConsumptionDetails(
        price_estimate=price_estimate,
        configuration=CostTrackingRegister.get_configuration(resource),
        last_update_time=_get_month_start(today),
    )
    details.save()
    price_estimate.create_ancestors()
    price_estimate.update_total()
    price_estimate.update_consumed()


def _update_ancestor_consumed(ancestor, today):
    price_estimate, _ = models.PriceEstimate.objects.get_or_create(scope=ancestor, month=today.month, year=today.year)
    resource_descendants = [descendant for descendant in price_estimate.get_descendants()
                            if isinstance(descendant.scope, structure_models.ResourceMixin)]
    price_estimate.consumed = sum([descendant.consumed for descendant in resource_descendants])
    price_estimate.save(update_fields=['consumed'])
