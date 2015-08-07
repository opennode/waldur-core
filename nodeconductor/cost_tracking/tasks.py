from celery import shared_task

from django.contrib.contenttypes.models import ContentType

from nodeconductor.billing.backend import BillingBackend
from nodeconductor.cost_tracking.models import DefaultPriceListItem


@shared_task(name='nodeconductor.cost_tracking.sync_pricelist')
def sync_pricelist():
    backend = BillingBackend()
    priceitems = DefaultPriceListItem.objects.filter(
        backend_product_id='').values_list('resource_content_type', flat=True).distinct()

    for cid in priceitems:
        content_type = ContentType.objects.get_for_id(cid)
        backend.propagate_pricelist(content_type)
