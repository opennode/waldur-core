from calendar import monthrange
from datetime import date, datetime
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError

from nodeconductor.billing.tasks import create_invoices
from nodeconductor.core.utils import datetime_to_timestamp
from nodeconductor.structure.models import Customer


class Command(BaseCommand):
    args = '<customer_id year month>'
    help = ('Create invoices for customers over provided month (last month by default).\n'
            'Arguments:\n'
            '   year (optional, current by default)      year of the provided month\n'
            '   month (optional, previous by default)    create invoices over provided month')
    option_list = (
        make_option(
            '--customer_uuid',
            dest='customer_uuid',
            default=None,
            help='Invoice will be created for customer with given UUID'),
        ) + BaseCommand.option_list

    def handle(self, *args, **options):
        if len(args) > 2 or len(args) == 1:
            raise CommandError('Only two or zero arguments can be provided.')

        try:
            if args:
                year = int(args[0])
                month = int(args[1])
            else:
                year = date.today().year
                month = date.today().month - 1
                if month == 0:
                    month = 12
                    year -= 1

            start_date = datetime(day=1, month=month, year=year)
        except ValueError:
            raise CommandError('Year and month should be valid values.')

        last_day = monthrange(year, month)[1]
        end_date = datetime(day=last_day, month=month, year=year)

        customer_uuid = options.get('customer_uuid')
        if customer_uuid:
            try:
                customer = Customer.objects.get(uuid=customer_uuid)
            except Customer.DoesNotExist:
                raise CommandError('Customer with given UUID does not exist')
            if not customer.billing_backend_id:
                raise CommandError('Selected customer does not have billing backend id')
            create_invoices.delay(customer_uuid, datetime_to_timestamp(start_date), datetime_to_timestamp(end_date))
        else:
            customers = Customer.objects.exclude(billing_backend_id='')
            for customer in customers:
                create_invoices.delay(customer.uuid.hex, datetime_to_timestamp(start_date),
                                      datetime_to_timestamp(end_date))
