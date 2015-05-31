import logging

from celery import shared_task
from datetime import date, timedelta

from nodeconductor.billing.backend import BillingBackend, whmcs
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
    customer = Customer.objects.get(uuid=customer_uuid)

    memberships = CloudProjectMembership.objects.filter(project__customer=customer)
    query = [{'field': 'timestamp', 'value': from_date, 'op': 'gt'},
             {'field': 'timestamp', 'value': to_date, 'op': 'lt'}]
    data = {
        'client_id': customer.billing_backend_id,
        'date': '{:%Y%m%d}'.format(date.today()),
        'due_date': '{:%Y%m%d}'.format(date.today() + timedelta(days=45)),
    }

    billing_backend = customer.get_billing_backend()

    for membership in memberships:
        backend = membership.cloud.get_backend()

        resources = {
            # Resource name: (priceList name, ceilometer name)
            'CPU': ('cpu_min', 'cpu'),
            'Memory': ('ram_mb', 'memory'),
            'Storage': ('storage_mb', 'disk.write.bytes'),
        }

        for name, values in resources.items():
            try:
                price = PriceList.objects.get(name=values[0]).price
                statistics = backend.get_ceilometer_statistics(membership, values[1], period, query)

                for usage in statistics:
                    usage_sum = usage.sum

                    if name == 'CPU':
                        # convert ns to min
                        usage_sum = round(usage_sum / (6 * pow(10, 10)))
                    elif name == 'Storage':
                        # convert bytes to megabytes
                        usage_sum = round(usage_sum / pow(1024, 2))

                    data['description'] = '%s usage from %s to %s.' % (name, from_date, to_date)
                    data['amount'] = str(float(price) * usage_sum)

                    billing_backend.api.create_invoice(**data)
            except PriceList.DoesNotExist:
                logger.info('Failed to create %s usage invoice for project %s.' %
                            (name, membership.project))
            else:
                logger.info('%s usage invoice for project %s successfully created.' %
                            (name, membership.project))
