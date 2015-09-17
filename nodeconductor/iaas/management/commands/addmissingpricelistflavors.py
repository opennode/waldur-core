from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from nodeconductor.cost_tracking.models import DefaultPriceListItem
from nodeconductor.iaas.models import Flavor, Instance


class Command(BaseCommand):

    def handle(self, *args, **options):
        instance_content_type = ContentType.objects.get_for_model(Instance)
        self.stdout.write('Checking flavors existance in DefaultPriceListItem table ...')
        for flavor in Flavor.objects.all():
            lookup_kwargs = {'item_type': 'flavor', 'key': flavor.name, 'resource_content_type': instance_content_type}
            if not DefaultPriceListItem.objects.filter(**lookup_kwargs).exists():
                item = DefaultPriceListItem(**lookup_kwargs)
                item.name = 'Flavor type: {}'.format(flavor.name)
                item.save()
                self.stdout.write('DefaultPriceListItem was created for flavor {}'.format(flavor.name))

        self.stdout.write('... Done')
