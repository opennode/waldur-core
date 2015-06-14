import logging
import importlib

from django.utils import six
from django.conf import settings
from django.core.files.base import ContentFile

from nodeconductor.billing.models import PriceList


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
                "Can't billing settings. "
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

    def sync_pricelist(self):
        # Update or create prices from backend
        cur_prices = {p.backend_id: p for p in PriceList.objects.all()}
        used_names = set(p.name for p in cur_prices.values())
        for product in self.api.get_products():
            cur_price = cur_prices.pop(product['backend_id'], None)
            if cur_price:
                cur_price.price = product['price']
                cur_price.save(update_fields=['price'])
            else:
                if product['name'] in used_names:
                    logger.warn("Product %s already exists in pricelist." % product['name'])
                    continue

                PriceList.objects.create(**product)
                used_names.add(product['name'])

        # Remove stale prices
        map(lambda i: i.delete(), cur_prices.values())

    def get_invoice_items(self, invoice_id):
        return self.api.get_invoice_items(invoice_id)


class DummyBillingAPI(object):
    pass
