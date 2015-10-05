from __future__ import unicode_literals

from django.core.management.base import BaseCommand
from django.db import transaction

from nodeconductor.quotas import models
from nodeconductor.quotas.utils import get_models_with_quotas


class Command(BaseCommand):
    """ Recalculate all quotas """

    def handle(self, *args, **options):
        # TODO: implement other quotas recalculation
        self.recalculate_global_quotas()
        self.delete_stale_quotas()

    def delete_stale_quotas(self):
        for model in get_models_with_quotas():
            for obj in model.objects.all():
                obj.quotas.exclude(name__in=model.QUOTAS_NAMES).delete()

    def recalculate_global_quotas(self):
        for model in get_models_with_quotas():
            if hasattr(model, 'GLOBAL_COUNT_QUOTA_NAME'):
                with transaction.atomic():
                    quota, _ = models.Quota.objects.get_or_create(name=model.GLOBAL_COUNT_QUOTA_NAME)
                    quota.usage = model.objects.count()
                    quota.save()
