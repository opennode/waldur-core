# -*- coding: utf-8

from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from nodeconductor.cost_tracking.models import DefaultPriceListItem


openstack_options = {
    'flavor': [
        ('g1.small1', 1),
        ('g1.small2', 2),
        ('g1.medium1', 3),
        ('g1.medium2', 4),
        ('g1.large1', 5),
        ('g1.large2', 6),
    ],
    'storage': [
        ('1 GB', 1)
    ],
    'license-os': [
        ('centos6', 1),
        ('centos7', 2),
        ('ubuntu', 3),
        ('rhel6', 4),
        ('rhel7', 5),
        ('windows', 6),
    ],
    'license-application': [
        ('wordpress', 1),
        ('postgresql', 2),
        ('zimbra', 3)
    ],
    'support': [
        ('basic', 1),
        ('premium', 2),
    ]
}


class Command(BaseCommand):

    def handle(self, *args, **options):
        from nodeconductor.openstack.models import OpenStackService
        os_content_type = ContentType.objects.get_for_model(OpenStackService)
        for category in ['flavor', 'storage', 'license-os', 'license-application', 'support']:
            option = openstack_options[category]
            for key, value in option:
                print key, value, os_content_type, category
                DefaultPriceListItem.objects.create(
                    service_content_type=os_content_type,
                    key=key,
                    value=value,
                    units='',
                    item_type=category
                )
        self.stdout.write('... Done')
