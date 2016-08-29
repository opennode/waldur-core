import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from nodeconductor.cost_tracking import models, CostTrackingRegister, tasks


class Command(BaseCommand):
    help = ("Delete all price estimates that are related to current month and "
            "create new ones based on current consumption.")

    def handle(self, *args, **options):
        today = timezone.now()
        with transaction.atomic():
            # Delete current month price estimates
            models.PriceEstimate.objects.filter(month=today.month, year=today.year).delete()
            # Create new estimates for resources and ancestors
            for resource_model in CostTrackingRegister.registered_resources:
                for resource in resource_model.objects.all():
                    _create_resource_estimate(resource, today)
            # recalculate consumed estimate
            tasks.recalculate_consumed_estimate()


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
