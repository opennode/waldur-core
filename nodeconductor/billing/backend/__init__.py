import logging
import importlib
import threading

from django.conf import settings


# A list of supported backends in a form of ('<backend_name>': '<backend_module>.<backend_class>')
BACKENDS = (
    ('WHMCS', 'whmcs.WHMCSAPI'),
)
DATA = threading.local().billing_data = {}
logger = logging.getLogger(__name__)


class BillingBackendError(Exception):
    pass


class BillingBackend(object):

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
            backends = dict(BACKENDS)
            backend_name = config.get('backend')
            if not backend_name or backend_name not in backends:
                raise BillingBackendError(
                    "Wrong backend name supplied '%s'. "
                    "Valid choices are: %s" % (backend_name, ', '.join(backends.keys())))

            try:
                mod, cls = backends[backend_name].split('.')
                backend = importlib.import_module('.' + mod, __package__)
                backend_cls = getattr(backend, cls)
            except ImportError:
                raise BillingBackendError(
                    "Can't find %s.%s module" % (__package__, mod))
            except AttributeError:
                raise BillingBackendError(
                    "Can't find %s.%s backend class" % (__package__, backends[backend_name]))
            else:
                self.api = backend_cls(**config)

    def get_or_create_client(self):
        if self.customer.backend_id:
            return self.customer.backend_id

        owner = self.customer.get_owners().first()
        backend_id = self.api.add_client(
            name=owner.full_name,
            email=owner.email,
            phone_number=owner.phone_number,
            organization=owner.organization)

        self.customer.save(update_fields=['backend_id'])

        return backend_id

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
