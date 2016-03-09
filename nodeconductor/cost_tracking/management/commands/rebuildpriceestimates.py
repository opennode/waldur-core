from django.core.management.base import BaseCommand

from nodeconductor.structure.models import Resource
from nodeconductor.cost_tracking.models import PriceEstimate


class Command(BaseCommand):

    def handle(self, *args, **options):
        for model in Resource.get_all_models():
            for resource in model.objects.all():
                PriceEstimate.update_ancestors_for_resource(resource)
