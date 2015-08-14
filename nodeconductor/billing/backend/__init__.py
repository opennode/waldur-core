import logging
import importlib

from django.utils import six
from django.conf import settings
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


class BillingBackendError(Exception):
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

    def __getattr__(self, name):
        return getattr(self.api, name)

    def get_or_create_client(self):
        if self.customer.billing_backend_id:
            return self.customer.billing_backend_id

        self.customer.billing_backend_id = self.api.add_client(
            name=self.customer.name,
            organization=self.customer.name,
            email="%s@example.com" % self.customer.uuid  # XXX: a fake email address unique to a customer
        )

        self.customer.save(update_fields=['billing_backend_id'])

        return self.customer.billing_backend_id

    def sync_customer(self):
        backend_id = self.get_or_create_client()
        client_details = self.api.get_client_details(backend_id)

        self.customer.balance = client_details['balance']
        self.customer.save(update_fields=['balance'])

    def sync_invoices(self):
        backend_id = self.get_or_create_client()

        # Update or create invoices from backend
        cur_invoices = {i.backend_id: i for i in self.customer.invoices.all()}
        for invoice in self.api.get_invoices(backend_id, with_pdf=True):
            cur_invoice = cur_invoices.pop(invoice['backend_id'], None)
            if cur_invoice:
                cur_invoice.date = invoice['date']
                cur_invoice.amount = invoice['amount']
                cur_invoice.status = invoice['status']
                cur_invoice.save(update_fields=['date', 'amount'])
            else:
                cur_invoice = self.customer.invoices.create(
                    backend_id=invoice['backend_id'],
                    date=invoice['date'],
                    amount=invoice['amount'],
                    status=invoice['status']
                )

            if 'pdf' in invoice:
                cur_invoice.pdf.delete()
                cur_invoice.pdf.save('Invoice-%d.pdf' % cur_invoice.uuid, ContentFile(invoice['pdf']))
                cur_invoice.save(update_fields=['pdf'])

        # Remove stale invoices
        map(lambda i: i.delete(), cur_invoices.values())

    def get_invoice_items(self, invoice_id):
        return self.api.get_invoice_items(invoice_id)

    def setup_product(self, resource, product_template_id):
        # - place an order and generate invoice
        options = resource.get_price_options()
        options = resource.order._propagate_default_options(options)

        client_id = self.get_or_create_client()
        order_id, product_id = self.api.add_order(
            client_id, product_template_id, resource.name, **options)

        resource.billing_backend_id = product_id
        resource.billing_backend_template_id = product_template_id
        resource.billing_backend_purchase_order_id = order_id
        resource.save(update_fields=['billing_backend_id',
                                     'billing_backend_template_id',
                                     'billing_backend_purchase_order_id'])

    def confirm_product_setup(self, resource):
        # - accept order
        self.api.accept_order(resource.billing_backend_purchase_order_id)

    def cancel_product_setup(self, resource):
        # - cancel order
        # TODO: cancel purchase if order already accepted
        self.api.cancel_order(resource.billing_backend_purchase_order_id)

    def update_product(self, resource, **options):
        # - get an upgrade price from API (invoice should be already present?)
        # - add upgrade amount as an item for last unpaid invoice or as billable item otherwise
        options = resource.order._propagate_default_options(options)
        client_id = self.get_or_create_client()

        # TODO: update product invoce instead of upgrading order
        self.api.upgrade_order(
            client_id, resource.billing_backend_id, resource.billing_backend_template_id, **options)

    def terminate_product(self, resource):
        # - change billing product status to 'terminated'
        # - deduct a price of remained days from final invoice
        if resource.billing_backend_id:
            # TODO: terminate instead of cancel
            self.api.cancel_purchase(resource.billing_backend_id)

    def get_total_cost_of_active_products(self):
        products = self.api.get_client_products(self.get_or_create_client())
        costs = [float(prod['recurring_amount']) for prod in products if prod['status'] == 'Active']
        return sum(costs)

    def get_orders(self):
        # XXX: This is fragile - different billing systems can return different orders,
        # after billing application stabilization we need to provide standard order structure
        return self.api.get_client_orders(self.get_or_create_client())


class DummyBillingAPI(object):
    def __getattr__(self, name):
        return lambda *args, **kwargs: None
