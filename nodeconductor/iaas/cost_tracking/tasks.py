import logging
import datetime
from celery import shared_task

from nodeconductor.cost_tracking.models import PriceEstimate
from nodeconductor.structure.models import Customer


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.iaas.cost_tracking.tasks.update_current_month_projected_estimate_for_customers')
def update_current_month_projected_estimate_for_all_customers():
    for customer in Customer.objects.exclude(billing_backend_id=''):
        update_current_month_projected_estimate_for_customer.delay(customer.uuid)


@shared_task
def update_current_month_projected_estimate_for_customer(customer_uuid):
    customer = Customer.objects.get(uuid=customer_uuid)
    try:
        backend = customer.get_billing_backend()
        monthly_cost = backend.get_total_cost_of_active_products()

        dt = datetime.datetime.now()
        estimate, created = PriceEstimate.objects.get_or_create(
            scope=customer,
            month=dt.month,
            year=dt.year
        )
        estimate.total = monthly_cost
        estimate.save()
    except:
        logger.error(
            'Failed to get price estimate for a customer with existing billing backend id. Stale customer?')
