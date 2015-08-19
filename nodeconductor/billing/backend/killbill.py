import logging
import requests
import lxml

from nodeconductor.billing.backend import BillingBackendError
from nodeconductor import __version__


logger = logging.getLogger(__name__)


class KillBillAPI(object):
    """ Killbill API client -- http://killbill.io/api/
        Test settings:

            NODECONDUCTOR['BILLING'] = {
                'backend': 'nodeconductor.billing.backend.killbill.KillBillAPI',
                'api_url': 'http://killbill.example.com:8080/1.0/kb/',
                'username': 'admin',
                'password': 'password',
                'api_key': 'bob',
                'api_secret': 'lazar',
            }
    """

    def __init__(self, api_url=None, username=None, password=None, api_key=None, api_secret=None, **kwargs):
        if not all((api_url, api_key, api_secret)):
            raise BillingBackendError(
                "Missed billing credentials. They must be supplied explicitly "
                "or defined within settings.NODECONDUCTOR.BILLING")

        self.credentials = dict(
            api_url=api_url,
            api_key=api_key,
            api_secret=api_secret,
            auth=(username, password))

        self.catalog = KillBill.Catalog(self.credentials)
        self.test = KillBill.Test(self.credentials)


class KillBill(object):

    class BaseResource(object):
        path = NotImplemented

        def __init__(self, credentials):
            self.__dict__ = credentials

        def __repr__(self):
            return self.api_url + self.path

        def get(self, *args, **kwargs):
            return self.request(self.path, method='GET', **kwargs)

        def post(self, *args, **kwargs):
            return self.request(self.path, method='POST', **kwargs)

        def request(self, url, method='GET', **kwargs):
            response_types = {'application/json': 'json', 'application/xml': 'xml'}
            headers = {'User-Agent': 'NodeConductor/%s' % __version__,
                       'Content-Type': 'application/json',
                       'X-Killbill-ApiKey': self.api_key,
                       'X-Killbill-ApiSecret': self.api_secret}

            response = getattr(requests, method.lower())(
                self.api_url + url, data=kwargs, auth=self.auth, headers=headers)

            response_type = response_types.get(response.headers.get('content-type'), '')
            if response.status_code != 200:
                reason = response.reason
                if response_type == 'json':
                    try:
                        reason = response.json()['message']
                    except ValueError:
                        pass
                raise BillingBackendError(
                    "%s. Request to Killbill backend failed: %s" % (response.status_code, reason))

            try:
                if response_type == 'xml':
                    data = lxml.etree.fromstring(
                        response.text.encode('utf-8'),
                        lxml.etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8'))

                elif response_type == 'json':
                    data = response.json()

                else:
                    raise BillingBackendError(
                        "Unknown content type %s" % response.headers.get('content-type'))

            except ValueError as e:
                raise BillingBackendError(
                    "Incorrect response from Killbill backend %s: e" % (self.url, e))

            return data

    class Catalog(BaseResource):
        path = 'catalog'

    class Invoice(BaseResource):
        path = 'invoices'

    class Test(BaseResource):
        path = 'test/clock'
