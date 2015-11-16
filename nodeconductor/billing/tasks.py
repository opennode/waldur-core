import logging
from datetime import timedelta, datetime

from celery import shared_task
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from nodeconductor.billing.backend import BillingBackend, BillingBackendError
from nodeconductor.billing.models import PaidResource
from nodeconductor.cost_tracking import CostTrackingRegister
from nodeconductor.cost_tracking.models import DefaultPriceListItem
from nodeconductor.structure import SupportedServices
from nodeconductor.structure.models import Customer, Resource


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.billing.debit_customers')
def debit_customers():
    """ Fetch a list of shared services (services based on shared settings).
        Calculate the amount of consumed resources "yesterday" (make sure this task executed only once a day)
        Reduce customer's balance accordingly
        Stop online resource if needed
    """

    date = datetime.now() - timedelta(days=1)
    start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=1, microseconds=-1)

    # XXX: it's just a placeholder, it doesn't work properly now nor implemented anyhow
    #      perhaps it should merely use price estimates..

    for model in SupportedServices.get_resource_models().keys():
        resources = model.objects.filter(
            service_project_link__service__settings__shared=True)

        for resource in resources:
            try:
                data = resource.get_cost(start_date, end_date)
            except NotImplementedError:
                continue
            else:
                resource.customer.debit_account(data['total_amount'])


@shared_task(name='nodeconductor.billing.sync_pricelist')
def sync_pricelist():
    backend = BillingBackend()
    try:
        backend.propagate_pricelist()
    except BillingBackendError as e:
        logger.error("Can't propagade pricelist to %s: %s", backend, e)


@shared_task(name='nodeconductor.billing.sync_billing_customers')
def sync_billing_customers(customer_uuids=None):
    if not isinstance(customer_uuids, (list, tuple)):
        customer_uuids = Customer.objects.all().values_list('uuid', flat=True)

    map(sync_billing_customer.delay, customer_uuids)


@shared_task
def sync_billing_customer(customer_uuid):
    customer = Customer.objects.get(uuid=customer_uuid)
    backend = customer.get_billing_backend()
    try:
        backend.sync_customer()
        backend.sync_invoices()
    except BillingBackendError as e:
        logger.error("Can't sync billing customer with %s: %s", backend, e)


@shared_task(name='nodeconductor.billing.update_today_usage')
def update_today_usage():
    """
    Calculate usage for all paid resources.

    Task counts exact usage amount for numerical options and boolean value for the rest.
    Example:
        2015-08-20 13:00    storage-1Gb         20
        2015-08-20 13:00    flavor-g1.small1    1
        2015-08-20 13:00    license-os-centos7  1
        2015-08-20 13:00    support-basic       1
    """

    nc_settings = getattr(settings, 'NODECONDUCTOR', {})
    if not nc_settings.get('ENABLE_ORDER_PROCESSING'):
        return

    for model in PaidResource.get_all_models():
        for resource in model.objects.all():
            update_today_usage_of_resource.delay(resource.to_string())


@shared_task
def update_today_usage_of_resource(resource_str):
    # XXX: this method does ignores cases then VM was offline or online for small periods of time.
    # It could to be rewritten if more accurate calculation will be needed
    with transaction.atomic():
        resource = next(Resource.from_string(resource_str))
        backend = CostTrackingRegister.get_resource_backend(resource)
        used_items = backend.get_used_items(resource)

        if not resource.billing_backend_id:
            logger.warning(
                "Can't update usage for resource %s which is not subscribed to backend", resource_str)
            return

        numerical = ['storage', 'users']  # XXX: use consistent method for usage calculation
        content_type = ContentType.objects.get_for_model(resource)

        units = {
            (item.item_type, None if item.item_type in numerical else item.key): item.units
            for item in DefaultPriceListItem.objects.filter(resource_content_type=content_type)}

        now = timezone.now()
        last_update_time = resource.last_usage_update_time or resource.created
        minutes_from_last_usage_update = (now - last_update_time).total_seconds() / 60

        usage = {}
        for item_type, key, val in used_items:
            if val:
                try:
                    unit = units[item_type, None if item_type in numerical else key]
                    usage_per_min = int(round(val * minutes_from_last_usage_update))
                    if usage_per_min:
                        usage[unit] = usage_per_min
                except KeyError:
                    logger.error("Can't find price for usage item %s:%s", key, val)

        resource.order.add_usage(usage)
        resource.last_usage_update_time = timezone.now()
        resource.save(update_fields=['last_usage_update_time'])
