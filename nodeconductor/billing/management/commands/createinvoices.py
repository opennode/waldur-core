from calendar import monthrange
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from nodeconductor.billing.tasks import create_invoices
from nodeconductor.structure.models import Customer


class Command(BaseCommand):
    args = '<year month>'
    help = """Create invoices for customers over provided month (last month by default).

Arguments:
    year(optional, current by default)    year of the provided month
    month(optional, previous by default)   create invoices over provided month"""

    def handle(self, *args, **options):
        if len(args) > 2:
            raise CommandError('Only year and month can be provided.')
        elif len(args) == 1:
            raise CommandError('You should provide both year and month.')

        try:
            year = int(args[0]) if len(args) == 2 else date.today().year
            month = int(args[1]) if len(args) == 2 else date.today().month - 1
        except ValueError:
            raise CommandError('Both arguments should be integers.')

        start_timestamp = date(day=1, month=month, year=year)
        last_day = monthrange(year, month)[1]
        end_timestamp = date(day=last_day, month=month, year=year)

        answer = raw_input('Are you sure you want to create invoices from %s to %s? [y/n]'
                           % (start_timestamp, end_timestamp))
        if answer != 'y':
            self.stdout.write('Aborting')
            return

        seconds = last_day * 24 * 60 * 60
        customers = Customer.objects.all()
        for customer in customers:
            create_invoices.delay(customer.uuid.hex, str(start_timestamp), str(end_timestamp), seconds)
