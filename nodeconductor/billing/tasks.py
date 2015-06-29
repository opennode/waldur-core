import logging

from datetime import date, timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from celery import shared_task

from nodeconductor.billing.backend import BillingBackend
from nodeconductor.billing.models import PriceList
from nodeconductor.core.utils import timestamp_to_datetime
from nodeconductor.iaas.models import CloudProjectMembership
from nodeconductor.logging.elasticsearch_client import ElasticsearchResultList
from nodeconductor.structure.models import Customer

logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.billing.sync_pricelist')
def sync_pricelist():
    backend = BillingBackend()
    backend.sync_pricelist()


def generate_usage_pdf(invoice, usage_data):
    # cleanup if usage_pdf already existed
    if invoice.usage_pdf is not None:
        invoice.usage_pdf.delete()

    # generate a new file
    invoice.usage_pdf.save('Usage-%d.pdf' % invoice.uuid, ContentFile("%s" % usage_data)) # TODO: replace with an actual
    invoice.save(update_fields=['usage_pdf'])


@shared_task(name='nodeconductor.billing.create_invoices')
def create_invoices(customer_uuid, start_date, end_date):
    try:
        customer = Customer.objects.get(uuid=customer_uuid)
    except Customer.DoesNotExist:
        logger.exception('Customer with uuid %s does not exist.', customer_uuid)
        return

    start_date = timestamp_to_datetime(start_date, replace_tz=False)  # XXX replacing TZ info causes nova client to fail
    end_date = timestamp_to_datetime(end_date, replace_tz=False)

    memberships = CloudProjectMembership.objects.filter(project__customer=customer)
    data = {
        'userid': customer.billing_backend_id,
        'date': '{:%Y%m%d}'.format(date.today()),
        'duedate': '{:%Y%m%d}'.format(date.today() + timedelta(days=45)),
    }

    billing_backend = customer.get_billing_backend()

    # collect_data
    billing_item_index = 1  # as injected into invoice, should start with 1 for whmcs
    projected_total = 0
    usage_data = {'reporting_period': (start_date, end_date), 'usage': {}}
    for membership in memberships:
        backend = membership.cloud.get_backend()
        usage = backend.get_nova_usage(membership, start_date, end_date)

        billing_category_name = membership.project.name
        # XXX a specific hack to support case when project resides in project_group
        if membership.project.project_groups.exists():
            billing_category_name = "%s: %s" % (membership.project.project_groups.first().name, membership.project.name)

        # empty placeholder for the usage data
        usage_data['usage'][billing_category_name] = {}

        # populate billing data with content
        billing_data = {}
        for field in ['cpu', 'disk', 'memory', 'servers']:
            billing_data[field] = usage[field]

        # process and aggregate license usage
        server_usage = usage.get('server_usages', [])
        for server in server_usage:
            usage_duration = server['hours']  # round up to a full hour
            server_uuid = server['instance_id']

            usage_data['usage'][billing_category_name][server_uuid] = {
                'hours': server['hours'],
                'flavor': server['flavor'],
                'disk': server['local_gb'],
                'memory': server['memory_mb'] / 1024.0,
                'started_at': server['started_at'],
                'ended_at': server['ended_at'],
                'state': server['state'],
                'uptime': server['uptime'],
                'name': server['name'],
            }
            # extract data for the usage report

            connected_licenses = lookup_instance_licenses_from_event_log(server_uuid)
            for license_type, license_service_type in connected_licenses:
                # XXX: license_service_type is not used here.
                usage_data['usage'][billing_category_name][server_uuid]['License %s' % license_type] = usage_duration
                billing_data[license_type] = billing_data.get(license_type, 0) + usage_duration

        # create invoices
        meters_mapping = settings.NODECONDUCTOR.get('BILLING')['openstack']['invoice_meters']

        for meter in meters_mapping.keys():
            name, price_name, unit = meters_mapping[meter]

            price = 0
            try:
                price = PriceList.objects.get(name=price_name).price
            except PriceList.DoesNotExist:
                logger.info('Failed to get price for %s in price list.', name)

            billing_value = round(billing_data.get(meter, 0))
            if billing_value == 0:
                continue

            data['itemdescription%s' % billing_item_index] = '%s: %s consumption of %s %s.' % \
                                                             (billing_category_name, name, billing_value, unit)
            cost = float(price) / 30 / 24 * billing_value
            data['itemamount%s' % billing_item_index] = str(cost)
            data['itemtaxed%s' % billing_item_index] = 0
            projected_total += cost
            billing_item_index += 1

    invoice_code = billing_backend.api.create_invoice(data)
    # create a preliminary invoice in NC
    invoice = customer.invoices.create(
        backend_id=invoice_code,
        date=date.today(),
        amount=projected_total,
        status='Unpaid'
    )
    # generate usage_pdf for the invoice
    generate_usage_pdf(invoice, usage_data)

    logger.info('WHMCS invoice with id %s for customer %s has been created.', invoice_code, customer)


def lookup_instance_licenses_from_event_log(instance_uuid):
    try:
        event = ElasticsearchResultList(None).filter(
            event_types=['iaas_instance_licenses_added'], instance_uuid=instance_uuid)[0][0]
    except IndexError:
        return []

    return zip(event['licenses_types'], event['licenses_services_types'])
