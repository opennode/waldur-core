# -*- coding: utf-8

from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from nodeconductor.cost_tracking.models import DefaultPriceListItem
from nodeconductor.cost_tracking import CostConstants
from nodeconductor.iaas.models import Instance


openstack_options = {
    CostConstants.PriceItem.FLAVOR: [
        (CostConstants.Flavor.OFFLINE, 0),
        ('g1.small1', 1),
        ('g1.small2', 2),
        ('g1.medium1', 3),
        ('g1.medium2', 4),
        ('g1.large1', 5),
        ('g1.large2', 6),
    ],
    CostConstants.PriceItem.STORAGE: [
        ('1 GB', 1),
    ],
    CostConstants.PriceItem.LICENSE_APPLICATION: [
        (name, idx) for idx, name in enumerate(dict(CostConstants.Application.CHOICES).keys(), start=1)
    ],
    CostConstants.PriceItem.LICENSE_OS: [
        (name, idx) for idx, name in enumerate(dict(CostConstants.Os.CHOICES).keys(), start=1)
    ],
    CostConstants.PriceItem.SUPPORT: [
        (name, idx) for idx, name in enumerate(dict(CostConstants.Support.CHOICES).keys(), start=1)
    ],
}


class Command(BaseCommand):

    def handle(self, *args, **options):
        content_type = ContentType.objects.get_for_model(Instance)
        for category, option in openstack_options.items():
            for key, value in option:
                self.stdout.write("[{}] {} -> {}".format(category, key, value))
                DefaultPriceListItem.objects.update_or_create(
                    resource_content_type=content_type,
                    item_type=category,  # e.g. 'flavor'
                    key=key,             # e.g. 'g1.small1'
                    defaults=dict(
                        value=value,     # e.g. '1'
                        units='',
                    )
                )
        self.stdout.write('... Done')
