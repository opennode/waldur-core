import os
import logging
import functools
import collections
import StringIO
import xhtml2pdf.pisa as pisa

from django.db import models
from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils.lru_cache import lru_cache
from django.utils.encoding import python_2_unicode_compatible
from django_fsm import transition, FSMIntegerField
from model_utils.models import TimeStampedModel

from nodeconductor.core import models as core_models
from nodeconductor.logging.log import LoggableMixin
from nodeconductor.cost_tracking.models import DefaultPriceListItem
from nodeconductor.billing.backend import BillingBackendError
from nodeconductor.billing.backend.killbill import UNIT_PREFIX


logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class Invoice(LoggableMixin, core_models.UuidMixin):

    class Permissions(object):
        customer_path = 'customer'

    customer = models.ForeignKey('structure.Customer', related_name='invoices')
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    date = models.DateField()
    pdf = models.FileField(upload_to='invoices', blank=True, null=True)
    usage_pdf = models.FileField(upload_to='invoices', blank=True, null=True)

    backend_id = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return "%s %.2f %s" % (self.date, self.amount, self.customer.name)

    def get_log_fields(self):
        return ('uuid', 'customer', 'amount', 'date', 'status')

    def get_billing_backend(self):
        return self.customer.get_billing_backend()

    def get_items(self):
        # TODO: create separate model for items
        if self.backend_id:
            backend = self.get_billing_backend()
            return backend.get_invoice_items(self.backend_id)
        else:
            # Dummy items
            return [
                {
                    "amount": "100",
                    "name": "storage-1GB"
                },
                {
                    "amount": "7.95",
                    "name": "flavor-g1.small1"
                }
            ]

    def generate_invoice_file_name(self, usage=False):
        name = '{}-invoice-{}'.format(self.date.strftime('%Y-%m-%d'), self.pk)
        if usage:
            name += '-usage'
        return name + '.pdf'

    def generate_pdf(self, invoice):
        projects = {}
        for item in invoice['items']:
            project = item['project']
            resource = item['resource']
            projects.setdefault(project, {'items': {}, 'amount': 0})
            projects[project]['amount'] += item['amount']
            projects[project]['items'].setdefault(resource, 0)
            projects[project]['items'][resource] += item['amount']

        number = 0
        projects = collections.OrderedDict(sorted(projects.items()))
        for project in projects:
            resources = []
            for resource, amount in sorted(projects[project]['items'].items()):
                number += 1
                resources.append((resource, {'amount': amount, 'number': number}))
            projects[project]['items'] = collections.OrderedDict(resources)

        # cleanup if pdf already existed
        if self.pdf is not None:
            self.pdf.delete()

        info = settings.NODECONDUCTOR.get('BILLING_INVOICE', {})
        logo = info.get('logo', None)
        if logo and not logo.startswith('/'):
            logo = os.path.join(settings.BASE_DIR, logo)

        result = StringIO.StringIO()
        pdf = pisa.pisaDocument(
            StringIO.StringIO(render_to_string('billing/invoice.html', {
                'customer': self.customer,
                'invoice': invoice,
                'projects': projects,
                'info': info,
                'logo': logo,
            })), result)

        # generate a new file
        if not pdf.err:
            self.pdf.save(self.generate_invoice_file_name(), ContentFile(result.getvalue()))
            self.save(update_fields=['pdf'])
        else:
            logger.error(pdf.err)

    def generate_usage_pdf(self, invoice):
        resources = {}
        pricelist = {p.units.replace(UNIT_PREFIX, ''): p for p in DefaultPriceListItem.objects.all()}

        for item in invoice['items']:
            price_item = pricelist.get(item['name'])
            if price_item:
                usage = item['amount'] / float(price_item.value)
                unit = ('GB/hour' if price_item.item_type == 'storage' else 'hour') + (
                    's' if usage > 1 else '')

                item['name'] = price_item.name
                item['usage'] = "{:.2f} {} x {:.2f} {}".format(
                    usage, unit, price_item.value, item['currency'])

            resource = item['resource']
            resources.setdefault(resource, {'items': [], 'amount': 0})
            resources[resource]['amount'] += item['amount']
            resources[resource]['items'].append(item)

        resources = collections.OrderedDict(sorted(resources.items()))

        # cleanup if pdf already existed
        if self.usage_pdf is not None:
            self.usage_pdf.delete()

        info = settings.NODECONDUCTOR.get('BILLING_INVOICE', {})
        logo = info.get('logo', None)
        if logo and not logo.startswith('/'):
            logo = os.path.join(settings.BASE_DIR, logo)

        result = StringIO.StringIO()
        pdf = pisa.pisaDocument(
            StringIO.StringIO(render_to_string('billing/usage_invoice.html', {
                'customer': self.customer,
                'invoice': invoice,
                'resources': resources,
                'logo': logo,
            })), result)

        # generate a new file
        if not pdf.err:
            self.usage_pdf.save(self.generate_invoice_file_name(usage=True), ContentFile(result.getvalue()))
            self.save(update_fields=['usage_pdf'])
        else:
            logger.error(pdf.err)


class Payment(LoggableMixin, TimeStampedModel, core_models.UuidMixin):

    class Permissions(object):
        customer_path = 'customer'

    class States(object):
        INIT = 0
        CREATED = 1
        APPROVED = 2
        CANCELLED = 3
        ERRED = 4

    STATE_CHOICES = (
        (States.INIT, 'Initial'),
        (States.CREATED, 'Created'),
        (States.APPROVED, 'Approved'),
        (States.ERRED, 'Erred'),
    )

    state = FSMIntegerField(default=States.INIT, choices=STATE_CHOICES)

    customer = models.ForeignKey('structure.Customer')
    amount = models.DecimalField(max_digits=9, decimal_places=2)

    # Payment ID is required and fetched from backend
    backend_id = models.CharField(max_length=255, null=True)

    # URL is fetched from backend
    approval_url = models.URLField()

    def __str__(self):
        return "%s %.2f %s" % (self.modified, self.amount, self.customer.name)

    def get_log_fields(self):
        return ('uuid', 'customer', 'amount', 'modified', 'status')

    @transition(field=state, source=States.INIT, target=States.CREATED)
    def set_created(self):
        pass

    @transition(field=state, source=States.CREATED, target=States.APPROVED)
    def set_approved(self):
        pass

    @transition(field=state, source=States.CREATED, target=States.CANCELLED)
    def set_cancelled(self):
        pass

    @transition(field=state, source='*', target=States.ERRED)
    def set_erred(self):
        pass


class PaidResource(models.Model):
    """ Extend Resource model with methods to track usage cost and handle orders """

    class Meta(object):
        abstract = True

    class Order(object):
        def __init__(self, instance):
            self.instance = instance

        def safe_method(func):
            """
            Catch billing errors and log them without re-raising

            Return format: <was method executed without error>, <error message>
            """
            @functools.wraps(func)
            def wrapped(self, *args, **kwargs):
                try:
                    func(self, *args, **kwargs)
                except BillingBackendError as e:
                    # silently fail with error log record
                    logger.error(
                        "Failed to perform order %s for resource %s: %s",
                        func.__name__, self.instance, e)
                    return False, str(e)
                else:
                    logger.info('Successfully perform order %s for resource %s.', func.__name__, self.instance)
                    return True, ''

            return wrapped

        @property
        def backend(self):
            return self.instance.service_project_link.service.customer.get_billing_backend()

        @safe_method
        def subscribe(self):
            self.backend.subscribe(self.instance)

        @safe_method
        def terminate(self):
            self.backend.terminate(self.instance)

        @safe_method
        def add_usage(self, usage_data):
            self.backend.add_usage_data(self.instance, usage_data)

        def reset(self):
            self.instance.billing_backend_id = ''
            self.instance.save(update_fields=['billing_backend_id'])

    billing_backend_id = models.CharField(max_length=255, blank=True, help_text='ID of a resource in backend')
    last_usage_update_time = models.DateTimeField(blank=True, null=True)

    @classmethod
    @lru_cache(maxsize=1)
    def get_all_models(cls):
        from nodeconductor.structure.models import Resource
        return [model for model in Resource.get_all_models() if issubclass(model, cls)]

    def __init__(self, *args, **kwargs):
        super(PaidResource, self).__init__(*args, **kwargs)
        self.order = self.Order(self)
