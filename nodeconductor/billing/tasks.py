import logging

from datetime import date, timedelta

from django.conf import settings
from celery import shared_task

from nodeconductor.billing.backend import BillingBackend
from nodeconductor.billing.models import PriceList
from nodeconductor.iaas.models import CloudProjectMembership
from nodeconductor.structure.models import Customer

logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.billing.sync_pricelist')
def sync_pricelist():
    backend = BillingBackend()
    backend.sync_pricelist()


@shared_task(name='nodeconductor.billing.create_invoices')
def create_invoices(customer_uuid, from_date, to_date, period=0):
    try:
        customer = Customer.objects.get(uuid=customer_uuid)
    except Customer.DoesNotExist:
        logger.exception('Customer with uuid %s does not exist.', customer_uuid)
        return

    memberships = CloudProjectMembership.objects.filter(project__customer=customer)
    query = [{'field': 'timestamp', 'value': from_date, 'op': 'gt'},
             {'field': 'timestamp', 'value': to_date, 'op': 'lt'}]
    data = {
        'userid': customer.billing_backend_id,
        'date': '{:%Y%m%d}'.format(date.today()),
        'duedate': '{:%Y%m%d}'.format(date.today() + timedelta(days=45)),
    }

    billing_backend = customer.get_billing_backend()

    for membership in memberships:
        backend = membership.cloud.get_backend()

        meters_mapping = settings.NODECONDUCTOR.get('BILLING')['openstack']['invoice_meters']

        for index, meter in enumerate(meters_mapping.keys(), 1):
            name, price_name, converter, unit = meters_mapping[meter]

            price = 0
            try:
                price = PriceList.objects.get(name=price_name).price
            except PriceList.DoesNotExist:
                logger.info('Failed to get price for %s in price list.', name)

            statistics = backend.get_ceilometer_statistics(membership, meter, period, query)
            for usage in statistics:
                usage_sum = getattr(backend, converter, usage.sum)(usage.sum)

                data['itemdescription%s' % index] = '%s usage %s %s from %s to %s.' % \
                                                    (name, round(usage_sum), unit, from_date, to_date)
                data['itemamount%s' % index] = str(float(price) * round(usage_sum))
                data['itemtaxed%s' % index] = 0

        invoice_code = billing_backend.api.create_invoice(data)
        logger.info('WHMCS invoice with id %s for project %s has been created.', invoice_code, membership.project)
