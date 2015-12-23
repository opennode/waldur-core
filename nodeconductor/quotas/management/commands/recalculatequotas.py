from __future__ import unicode_literals

from django.core.management.base import BaseCommand
from django.db import transaction

from nodeconductor.quotas import models, fields
from nodeconductor.quotas.utils import get_models_with_quotas


class Command(BaseCommand):
    """ Recalculate all quotas """

    def handle(self, *args, **options):
        # TODO: implement other quotas recalculation
        # TODO: implement global stale quotas deletion
        self.delete_stale_quotas()
        self.recalculate_global_quotas()
        self.recalculate_count_quotas()
        self.recalculate_aggregate_quotas()

    def delete_stale_quotas(self):
        for model in get_models_with_quotas():
            for obj in model.objects.all():
                quotas_names = model.QUOTAS_NAMES + [f.name for f in model.get_quotas_fields()]
                obj.quotas.exclude(name__in=quotas_names).delete()

    def recalculate_global_quotas(self):
        for model in get_models_with_quotas():
            if hasattr(model, 'GLOBAL_COUNT_QUOTA_NAME'):
                with transaction.atomic():
                    quota, _ = models.Quota.objects.get_or_create(name=model.GLOBAL_COUNT_QUOTA_NAME)
                    quota.usage = model.objects.count()
                    quota.save()

    def recalculate_count_quotas(self):
        for model in get_models_with_quotas():
            for counter_field in model.get_quotas_fields(field_class=fields.CounterQuotaField):
                for instance in model.objects.all():
                    counter_field.recalculate_usage(scope=instance)

    def recalculate_aggregate_quotas(self):
        for model in get_models_with_quotas():
            for aggregator_field in model.get_quotas_fields(field_class=fields.AggregatorQuotaField):
                for instance in model.objects.all():
                    aggregator_field.recalculate_usage(scope=instance)
