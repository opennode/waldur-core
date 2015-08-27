import logging

from celery import shared_task
from datetime import timedelta, datetime

from nodeconductor.billing.backend import BillingBackend, BillingBackendError
from nodeconductor.structure import SupportedServices


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
