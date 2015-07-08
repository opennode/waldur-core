import StringIO
import logging

from datetime import date, timedelta, datetime

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils.lru_cache import lru_cache
from celery import shared_task
import xhtml2pdf.pisa as pisa

from nodeconductor.backup.models import Backup
from nodeconductor.billing.backend import BillingBackend
from nodeconductor.billing.models import PriceList
from nodeconductor.core.utils import timestamp_to_datetime
from nodeconductor.iaas.backend import CloudBackendError
from nodeconductor.iaas.models import CloudProjectMembership, Instance
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

    projects = usage_data['usage']
    for project_name, instances in projects.items():
        for instance in instances:
            instance['started_at'] = datetime.strptime(instance['started_at'], '%Y-%m-%dT%H:%M:%S.%f')
            if instance['ended_at']:
                instance['ended_at'] = datetime.strptime(instance['ended_at'], '%Y-%m-%dT%H:%M:%S.%f')
            instance['hours'] = round(instance['hours'], 2)

        projects[project_name] = sorted(instances, key=lambda i: (i['name']))

    context = {
        'reporting_period': usage_data['reporting_period'],
        'customer_name': usage_data['customer_name'],
        'projects': projects,
    }

    result = StringIO.StringIO()
    pdf = pisa.pisaDocument(
        StringIO.StringIO(render_to_string('usage_report.html', context)),
        result
    )
    # generate a new file
    if not pdf.err:
        invoice.usage_pdf.save('Usage-%d.pdf' % invoice.uuid, ContentFile(result.getvalue()))
        invoice.save(update_fields=['usage_pdf'])
    else:
        logger.error(pdf.err)


@lru_cache(maxsize=1)
def get_customer_usage_data(customer, start_date, end_date):
    start_date = timestamp_to_datetime(start_date, replace_tz=False)  # XXX replacing TZ info causes nova client to fail
    end_date = timestamp_to_datetime(end_date, replace_tz=False)

    memberships = CloudProjectMembership.objects.filter(project__customer=customer)
    data = {
        'userid': customer.billing_backend_id,
        'date': '{:%Y%m%d}'.format(date.today()),
        'duedate': '{:%Y%m%d}'.format(date.today() + timedelta(days=45)),
    }

    # collect_data
    billing_item_index = 1  # as injected into invoice, should start with 1 for whmcs
    projected_total = 0
    usage_data = {'reporting_period': (start_date, end_date), 'customer_name': customer.name, 'usage': {}}
    for membership in memberships:
        backend = membership.cloud.get_backend()
        try:
            usage = backend.get_nova_usage(membership, start_date, end_date)
        except CloudBackendError:
            usage = {}

        billing_category_name = membership.project.name
        # XXX a specific hack to support case when project resides in project_group
        if membership.project.project_groups.exists():
            billing_category_name = "%s: %s" % (membership.project.project_groups.first().name, membership.project.name)

        # empty placeholder for the usage data
        usage_data['usage'][billing_category_name] = []

        # populate billing data with content
        billing_data = {}
        for field in ['cpu', 'disk', 'memory', 'servers']:
            billing_data[field] = usage.get(field, 0)

        # process and aggregate license usage
        server_usage = usage.get('server_usages', [])
        for server in server_usage:
            usage_duration = server['hours']  # round up to a full hour
            server_uuid = server['instance_id']

            usage_data['usage'][billing_category_name].append({
                'hours': server['hours'],
                'flavor': server['flavor'],
                'disk': server['local_gb'],
                'memory': server['memory_mb'] / 1024.0,
                'cores': server['vcpus'],
                'started_at': server['started_at'],
                'ended_at': server['ended_at'],
                'state': server['state'],
                'uptime': server['uptime'],
                'name': server['name'],
                'backups_disk': 0,
            })
            # extract data for the usage report

            connected_licenses = lookup_instance_licenses_from_event_log(server_uuid)
            for license_type, license_service_type in connected_licenses:
                # XXX: license_service_type is not used here.
                usage_data['usage'][billing_category_name][server_uuid]['License %s' % license_type] = usage_duration
                billing_data[license_type] = billing_data.get(license_type, 0) + usage_duration

            # XXX: Only existed backups are connected to existed instances
            try:
                instance = Instance.objects.get(uuid=server_uuid)
                ct = ContentType.objects.get_for_model(instance)
                backups = Backup.objects.filter(
                    object_id=instance.id, content_type=ct, created_at__lte=end_date)
                for backup in backups:
                    usage_data['backups_disk'] += backup.metadata.get('data_snapshot_size', 0) / 1024.0
                    usage_data['backups_disk'] += backup.metadata.get('data_volume_size', 0) / 1024.0
            except Instance.DoesNotExist:
                pass

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

    return usage_data, data, projected_total


# TODO: Refactor this tasks and related method: split it into more readable functions, move logic to models.
# Use data from django-revisions, not events (if this is possible).
@shared_task(name='nodeconductor.billing.create_invoices')
def create_invoices(customer_uuid, start_date, end_date):
    try:
        customer = Customer.objects.get(uuid=customer_uuid)
    except Customer.DoesNotExist:
        logger.exception('Customer with uuid %s does not exist.', customer_uuid)
        return

    billing_backend = customer.get_billing_backend()
    usage_data, data, projected_total = get_customer_usage_data(customer, start_date, end_date)

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
