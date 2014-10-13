from __future__ import unicode_literals

from django.core.management.base import BaseCommand, CommandError

from nodeconductor.structure import models as structure_models
from nodeconductor.cloud import models


class Command(BaseCommand):
    help = ('Starts clouds synchronization. Usage examples: \n'
            ' manage.py synccloud `cloud_uuid` - synchronizes cloud with given uuid \n'
            ' manage.py synccloud --customer=`customer_uuid` --all - synchronizes '
            'all clouds belonging to a customer with a given UUID\n'
            ' manage.py synccloud --all - synchronizes all clouds')

    def add_arguments(self, parser):
        # cloud uuid
        parser.add_argument('uuid', nargs='+', defaule=None, type=str)
        parser.add_argument('--all', dest='all', default=False,
                            help='Add this flag if all clouds have to be synchronized')
        parser.add_argument('--customer', dest='customer', default=None, help="Customers uuid")

    def _sync_cloud(self, uuid):
        try:
            cloud = models.Cloud.objects.get(uuid=uuid)
            cloud.sync()
        except models.Cloud.DoesNotExist:
            raise CommandError('No cloud with uuid: %s' % str(uuid))

    def _sync_all_clouds(self, customer):
        clouds = models.Cloud.objects.all()
        if customer is not None:
            clouds = clouds.filter(customer=customer)
        for cloud in clouds:
            cloud.sync()

    def _get_customer_or_none(self, options):
        if 'customer' in options:
            try:
                return structure_models.Customer.objects.get(uuid=options['customer'])
            except structure_models.Customer.DoesNotExist:
                raise CommandError('No customer with uuid: %s' % str(options['customer']))
        else:
            return None

    def handle(self, *args, **options):
        if args:
            for uuid in args:
                self._sync_cloud(uuid)
        else:
            customer = self._get_customer_or_none(options)
            if 'all' in options:
                self._sync_all_clouds(customer)
            else:
                raise CommandError('Error: Clouds uuids or `--all` option have to be defined')
