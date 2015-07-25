# -*- coding: utf-8

from __future__ import unicode_literals

import random

from django.core.management.base import BaseCommand
from django.utils import timezone

from nodeconductor.cost_tracking import models


class Command(BaseCommand):

    def handle(self, *args, **options):
        current_month = timezone.now().month
        current_year = timezone.now().year
        for model in models.PriceEstimate.get_estimated_models():
            self.stdout.write('Creating price estimates for all instance of model: {} ...'.format(model.__name__))
            estimates = []
            for obj in model.objects.all():
                self.stdout.write(' - price estimates for object: {}'.format(obj))
                for i in range(6):
                    year = current_year
                    month = current_month - i
                    if month < 1:
                        year = current_year - 1
                        month += 12
                    estimates.append(
                        models.PriceEstimate(
                            scope=obj,
                            total=random.randint(100, 2000),
                            details={
                                'ram': random.randint(50, 200),
                                'disk': random.randint(50, 200),
                                'cpu': random.randint(50, 200),
                            },
                            year=year,
                            month=month,
                        )
                    )
            models.PriceEstimate.objects.bulk_create(estimates)
            self.stdout.write('... Done')
