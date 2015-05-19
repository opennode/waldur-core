import hashlib
import requests

from nodeconductor.billing.backend import BillingBackendError
from nodeconductor.core.utils import pwgen
from nodeconductor import __version__


class WHMCSAPI(object):

    def __init__(self, api_url=None, username=None, password=None, **kwargs):
        if not all((api_url, username, password)):
            raise BillingBackendError(
                "Missed billing credendials. They must be supplied explicitly "
                "or defined within settings.NODECONDUCTOR.BILLING")

        self.api_url = api_url
        self.credendials = dict(
            username=username,
            password=hashlib.md5(password).hexdigest())

    def request(self, action, **kwargs):
        data = {'action': action, 'responsetype': 'json'}
        data.update(self.credendials)
        data.update(kwargs)

        headers = {'User-Agent': 'NodeConductor/%s' % __version__,
                   'Content-Type': 'application/x-www-form-urlencoded'}

        response = requests.post(self.api_url, data=data, headers=headers)
        if response.status_code != 200:
            raise BillingBackendError(
                "%s. Request to WHMCS backend failed: %s" % (response.status_code, response.text))

        data = response.json()
        status = data.pop('result')
        if status != 'success':
            raise BillingBackendError(
                "Can't perform '%s' on WHMCS backend: %s" % (action, data['message']))

        return data

    def add_client(self, name=None, email=None, organization=None, phone_number=None, **kwargs):
        names = name.split() if name else ['']
        data = self.request(
            'addclient',
            firstname=names[0],
            lastname=' '.join(names[1:]) or '-',
            companyname=organization,
            email=email,
            address1='n/a',
            city='n/a',
            state='n/a',
            postcode='00000',
            country='US',
            phonenumber=phone_number or '1234567',
            password2=pwgen())

        return data['clientid']

    def get_client_details(self, client_id):
        data = self.request('getclientsdetails', clientid=client_id)
        return {'balance': data.get('credit')}
