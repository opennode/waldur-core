from calendar import monthrange
from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from nodeconductor.billing.tasks import create_invoices
from nodeconductor.core.utils import datetime_to_timestamp
from nodeconductor.structure.models import Customer


class Command(BaseCommand):
    args = '<customer_id year month>'
    help = """Create invoices for customers over provided month (last month by default).

Arguments:
    customer_id (optional, all by default)   customer UUID to create invoices for
    year (optional, current by default)      year of the provided month
    month (optional, previous by default)    create invoices over provided month"""

    def handle(self, *args, **options):
        if len(args) > 3:
            raise CommandError('Only three arguments can be provided.')

        try:
            if len(args) == 2:
                year = int(args[0])
                month = int(args[1])
            elif len(args) == 3:
                year = int(args[1])
                month = int(args[2])
            else:
                year = date.today().year
                month = date.today().month - 1

            start_date = datetime(day=1, month=month, year=year)
        except ValueError:
            raise CommandError('Year and month should be valid values.')

        last_day = monthrange(year, month)[1]
        end_date = datetime(day=last_day, month=month, year=year)

        is_customer_id = len(args) in (1, 3)
        if is_customer_id:
            create_invoices.delay(args[0], datetime_to_timestamp(start_date), datetime_to_timestamp(end_date))
        else:
            customers = Customer.objects.exclude(billing_backend_id='')
            for customer in customers:
                create_invoices.delay(customer.uuid.hex, datetime_to_timestamp(start_date),
                                      datetime_to_timestamp(end_date))
