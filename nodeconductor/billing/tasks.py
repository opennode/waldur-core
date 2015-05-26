from celery import shared_task

from nodeconductor.billing.backend import BillingBackend
from nodeconductor.structure.models import Customer


@shared_task(name='nodeconductor.billing.sync_pricelist')
def sync_pricelist():
    backend = BillingBackend()
    backend.sync_pricelist()


@shared_task(name='nodeconductor.billing.sync_invoices')
def sync_invoices(customer_uuid):
    customer = Customer.objects.get(uuid=customer_uuid)

    backend = customer.get_billing_backend()
    backend.sync_invoices()
