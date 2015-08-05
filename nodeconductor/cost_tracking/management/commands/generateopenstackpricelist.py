# -*- coding: utf-8

from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from nodeconductor.cost_tracking.models import DefaultPriceListItem
from nodeconductor.cost_tracking import PriceItemTypes, OsTypes, ApplicationTypes
from nodeconductor.iaas.models import Instance


openstack_options = {
    PriceItemTypes.FLAVOR: [
        ('g1.small1', 1),
        ('g1.small2', 2),
        ('g1.medium1', 3),
        ('g1.medium2', 4),
        ('g1.large1', 5),
        ('g1.large2', 6),
    ],
    PriceItemTypes.STORAGE: [
        ('1 GB', 1),
    ],
    PriceItemTypes.LICENSE_APPLICATION: [
        (name, idx) for idx, name in enumerate(dict(ApplicationTypes.CHOICES).keys(), start=1)
    ],
    PriceItemTypes.LICENSE_OS: [
        (name, idx) for idx, name in enumerate(dict(OsTypes.CHOICES).keys(), start=1)
    ],
    PriceItemTypes.SUPPORT: [
        ('basic', 1),
        ('premium', 2),
    ],
}


class Command(BaseCommand):

    def handle(self, *args, **options):
        content_type = ContentType.objects.get_for_model(Instance)
        for category, option in openstack_options.items():
            for key, value in option:
                print category, key, value, content_type
                DefaultPriceListItem.objects.update_or_create(
                    service_content_type=content_type,
                    item_type=category,  # e.g. 'flavor'
                    key=key,             # e.g. 'g1.small1'
                    defaults=dict(
                        value=value,     # e.g. '1'
                        units='',
                    )
                )
        self.stdout.write('... Done')
