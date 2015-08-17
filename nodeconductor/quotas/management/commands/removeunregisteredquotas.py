from __future__ import unicode_literals

from django.core.management.base import BaseCommand

from nodeconductor.quotas.utils import get_models_with_quotas


class Command(BaseCommand):
    """ Remove unregistered quotas """

    def handle(self, *args, **options):
        for model in get_models_with_quotas():
            for instance in model.objects.all():
                instance.quotas.exclude(name__in=model.QUOTAS_NAMES).delete()
