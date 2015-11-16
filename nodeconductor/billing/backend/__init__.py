import logging
import importlib

from django.utils import six
from django.conf import settings


logger = logging.getLogger(__name__)


class BillingBackendError(Exception):
    pass


class NotFoundBillingBackendError(BillingBackendError):
    pass


class BillingBackend(object):
    """ General billing backend.
        Utilizes particular backend API client depending on django settings.
    """

    def __init__(self, customer=None):
        self.customer = customer
        dummy = settings.NODECONDUCTOR.get('BILLING_DUMMY')
        config = settings.NODECONDUCTOR.get('BILLING')

        if dummy:
            logger.warn(
                "Dummy backend for billing is used, "
                "set BILLING_DUMMY to False to disable dummy backend")
            self.api = DummyBillingAPI()
            self.api_url = ':dummy:'
        elif not config:
            raise BillingBackendError(
                "Can't find billing settings. "
                "Please provide settings.NODECONDUCTOR.BILLING dictionary.")
        else:
            backend_path = config.get('backend', '')
            try:
                path_bits = backend_path.split('.')
                class_name = path_bits.pop()
                backend = importlib.import_module('.'.join(path_bits))
                backend_cls = getattr(backend, class_name)
            except (AttributeError, IndexError):
                raise BillingBackendError(
                    "Invalid backend supplied: %s" % backend_path)
            except ImportError as e:
                six.reraise(BillingBackendError, e)
            else:
                self.api = backend_cls(**config)
                self.api_url = config.get('api_url', ':unknown:')

    def __getattr__(self, name):
        try:
            return getattr(self.api, name)
        except AttributeError:
            raise BillingBackendError(
                "Method '%s' is not implemented for class '%s'" % (name, self.api.__class__.__name__))

    def __repr__(self):
        return 'Billing backend %s' % self.api_url

    def get_or_create_client(self):
        try:
            client = self.api.get_client_by_uuid(self.customer.uuid.hex)
            if self.customer.billing_backend_id != client['accountId']:
                self.customer.billing_backend_id = client['accountId']
                self.customer.save(update_fields=['billing_backend_id'])
        except NotFoundBillingBackendError:
            self.customer.billing_backend_id = self.api.add_client(
                email="%s@example.com" % self.customer.uuid,  # XXX: a fake email address unique to a customer
                name=self.customer.name,
                uuid=self.customer.uuid.hex)
            self.customer.save(update_fields=['billing_backend_id'])

        return self.customer.billing_backend_id

    def sync_customer(self):
        backend_id = self.get_or_create_client()
        client_details = self.api.get_client_details(backend_id)

        self.customer.balance = client_details['balance']
        self.customer.save(update_fields=['balance'])

    def sync_invoices(self):
        client_id = self.get_or_create_client()

        # Update or create invoices from backend
        cur_invoices = {i.backend_id: i for i in self.customer.invoices.all()}
        for invoice in self.api.get_invoices(client_id):
            cur_invoice = cur_invoices.pop(invoice['backend_id'], None)
            if cur_invoice:
                cur_invoice.date = invoice['date']
                cur_invoice.amount = invoice['amount']
                cur_invoice.save(update_fields=['date', 'amount'])
            else:
                cur_invoice = self.customer.invoices.create(
                    backend_id=invoice['backend_id'],
                    date=invoice['date'],
                    amount=invoice['amount'])

            cur_invoice.generate_pdf(invoice)
            cur_invoice.generate_usage_pdf(invoice)

        # Remove stale invoices
        map(lambda i: i.delete(), cur_invoices.values())

    def subscribe(self, resource):
        client_id = self.get_or_create_client()
        resource.billing_backend_id = self.api.add_subscription(client_id, resource)
        resource.save(update_fields=['billing_backend_id'])

    def terminate(self, resource):
        self.api.del_subscription(resource.billing_backend_id)
        resource_model = resource.__class__
        if resource_model.objects.filter(pk=resource.pk).exists():
            resource.billing_backend_id = ''
            resource.save(update_fields=['billing_backend_id'])

    def add_usage_data(self, resource, usage_data):
        self.api.add_usage(resource.billing_backend_id, usage_data)

    def get_invoice_estimate(self, resource):
        client_id = self.get_or_create_client()
        return self.api.get_dry_invoice(client_id, resource.billing_backend_id)


class DummyBillingAPI(object):
    def __getattr__(self, name):
        return lambda *args, **kwargs: None
