import logging
import importlib
import threading

from django.utils import six
from django.conf import settings


DATA = threading.local().billing_data = {}
logger = logging.getLogger(__name__)


class BillingBackendError(Exception):
    pass


class BillingBackend(object):
    """ General billing backend. Expects django settings as follow:

            NODECONDUCTOR['BILLING'] = {
                'backend': 'nodeconductor.billing.backend.whmcs.WHMCSAPI',
                'api_url': 'http://demo.whmcs.com/includes/api.php',
                'username': 'Admin',
                'password': 'demo',
            }
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

        owner = self.customer.get_owners().first()
        self.customer.billing_backend_id = self.api.add_client(
            name=owner.full_name,
            email=owner.email,
            phone_number=owner.phone_number,
            organization=owner.organization)

        self.customer.save(update_fields=['billing_backend_id'])

        return self.customer.billing_backend_id

    def sync_customer(self):
        backend_id = self.get_or_create_client()
        client_details = self.api.get_client_details(backend_id)

        self.customer.balance = client_details['balance']
        self.customer.save(update_fields=['balance'])


class DummyBillingAPI(object):

    def add_client(self, *args, **kwargs):
        raise NotImplementedError

    def get_client_details(self, client_id):
        raise NotImplementedError
