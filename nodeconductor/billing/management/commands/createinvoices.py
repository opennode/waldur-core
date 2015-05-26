import datetime

from django.core.management.base import BaseCommand

from nodeconductor.billing.models import Invoice
from nodeconductor.billing.tasks import sync_invoices
from nodeconductor.iaas.models import CloudProjectMembership
from nodeconductor.structure.models import Customer


class Command(BaseCommand):
    # TODO: help and args

    def handle(self, *args, **options):
        customers = Customer.objects.all()
        for customer in customers:
            memberships = CloudProjectMembership.objects.filter(project__customer=customer)

            for membership in memberships:
                for quota in membership.quotas.all():
                    Invoice.objects.create(customer=customer,
                                           date=datetime.date.today(),
                                           amount=quota.usage
                                           )

            sync_invoices.delay(customer.uuid.hex)
