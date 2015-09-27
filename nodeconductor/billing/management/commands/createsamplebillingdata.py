
from django.core.management.base import BaseCommand

from nodeconductor.billing.models import Invoice
from nodeconductor.structure.models import Customer


class Command(BaseCommand):
    help = 'Create dummy invoices & price list'

    def handle(self, *args, **options):
        invoices = (
            {'date': '2015-03-15', 'amount': 12.95},
            {'date': '2015-02-07', 'amount': 319.00},
            {'date': '2014-10-10', 'amount': 7.95},
            {'date': '2014-10-17', 'amount': 2.45},
            {'date': '2014-10-21', 'amount': 10.00},
        )

        customer = Customer.objects.first()
        if customer:
            cur_invoices = set(i.date for i in customer.invoices.all())
            for invoice in invoices:
                if invoice['date'] not in cur_invoices:
                    inv = Invoice.objects.create(customer=customer, **invoice)
                    self.stdout.write('Created invoice: %s' % inv)
        else:
            self.stdout.write('None customer found. Skip.')
