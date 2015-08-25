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
        return getattr(self.api, name)

    def __repr__(self):
        return 'Billing backend %s' % self.api_url

    def get_or_create_client(self):
        if self.customer.billing_backend_id:
            return self.customer.billing_backend_id

        self.customer.billing_backend_id = self.api.add_client(
            name=self.customer.name,
            uuid=self.customer.uuid.hex)

        self.customer.save(update_fields=['billing_backend_id'])

        return self.customer.billing_backend_id

    def sync_customer(self):
        backend_id = self.get_or_create_client()
        client_details = self.api.get_client_details(backend_id)

        self.customer.balance = client_details['balance']
        self.customer.save(update_fields=['balance'])

    def subscribe(self, resource):
        client_id = self.get_or_create_client()
        resource.billing_backend_id = self.api.add_subscription(client_id, resource)
        resource.save(update_fields=['billing_backend_id'])

    def terminate(self, resource):
        self.api.del_subscription(resource.billing_backend_id)
        resource.billing_backend_id = ''
        resource.save(update_fields=['billing_backend_id'])

    def get_total_cost_of_active_products(self):
        return self.api.get_total_cost_of_active_products(self.get_or_create_client())

    def get_orders(self):
        return self.api.get_client_orders(self.get_or_create_client())


class DummyBillingAPI(object):
    def __getattr__(self, name):
        return lambda *args, **kwargs: None
