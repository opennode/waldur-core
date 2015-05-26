from celery import shared_task

from nodeconductor.billing.backend import BillingBackend


@shared_task(name='nodeconductor.billing.sync_pricelist')
def sync_pricelist():
    backend = BillingBackend()
    backend.sync_pricelist()
