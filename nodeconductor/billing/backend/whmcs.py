import re
import urllib
import hashlib
import datetime
import urlparse
import requests
import logging

from nodeconductor.billing.backend import BillingBackendError
from nodeconductor.core.utils import pwgen
from nodeconductor import __version__


logger = logging.getLogger(__name__)


class WHMCSAPI(object):
    """ WHMCS API client -- http://docs.whmcs.com/API
        Test settings:

            NODECONDUCTOR['BILLING'] = {
                'backend': 'nodeconductor.billing.backend.whmcs.WHMCSAPI',
                'api_url': 'http://demo.whmcs.com/includes/api.php',
                'username': 'Admin',
                'password': 'demo',
                'currency_code': 1,
                'currency_name': 'USD',
            }
    """

    class Request(object):
        class ResultSet(object):
            def __new__(cls, request, data):
                if request.resultset_path:
                    instance = object.__new__(cls)
                    instance.start = int(data.pop('startnumber', 0))
                    instance.limit = int(data.pop('numreturned', 0))
                    instance.total = int(data.pop('totalresults', 0))
                    return instance

                return type(cls.__name__, (dict,), {})(data)

            def __init__(self, request, data):
                self.request = request
                self.results = self._get_results(data)
                self.current = 0

            def __iter__(self):
                return self

            def _get_results(self, data):
                try:
                    return reduce(dict.get, self.request.resultset_path.split('.'), data)
                except TypeError:
                    logging.debug('Unexpected structure received as a response. Empty or missing response. %s', data)
                    raise StopIteration

            def __next__(self):
                return self.next()

            def next(self):
                try:
                    val = self.results.pop(0)
                except IndexError:
                    if self.current >= self.total:
                        raise StopIteration
                    else:
                        self.start = self.start + self.limit
                        self.results = self._get_results(
                            self.request.fetch(limitstart=self.start, limitnum=self.limit))
                        return self.next()
                else:
                    self.current += 1
                    return val

        def __init__(self, url, request_data, resultset_path=None):
            self.url = url
            self.request_data = request_data
            self.resultset_path = resultset_path

        def data(self):
            return self.ResultSet(self, self.fetch())

        def fetch(self, **kwargs):
            headers = {'User-Agent': 'NodeConductor/%s' % __version__,
                       'Content-Type': 'application/x-www-form-urlencoded'}

            data = self.request_data
            data.update(**kwargs)

            response = requests.post(self.url, data=data, headers=headers, verify=False)
            if response.status_code != 200:
                raise BillingBackendError(
                    "%s. Request to WHMCS backend failed: %s" %
                    (response.status_code, response.text))

            data = response.json()
            status = data.pop('result', None) or data.pop('status')
            if status != 'success':
                raise BillingBackendError(
                    "Can't perform '%s' on WHMCS backend: %s" %
                    (self.request_data['action'], data['message']))

            return data

    def __init__(self, api_url=None, username=None, password=None, currency_code=1, currency_name='USD', **kwargs):
        if not all((api_url, username, password)):
            raise BillingBackendError(
                "Missed billing credentials. They must be supplied explicitly "
                "or defined within settings.NODECONDUCTOR.BILLING")

        self.api_url = api_url
        self.username = username
        self.password = password
        self.currency_code = currency_code
        self.currency_name = currency_name

    def _parse_date(self, date):
        try:
            return datetime.datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError as e:
            raise BillingBackendError("Can't parse date %s: %s" % (date, e))

    def _get_backend_url(self, path, args=()):
        url_parts = list(urlparse.urlparse(self.api_url))
        # XXX: a hack to support default deployments of whmcs that expose whmcs as the suffix name
        if url_parts[2].startswith('/whmcs/'):
            path = '/whmcs/%s' % path
        url_parts[2] = path
        url_parts[4] = urllib.urlencode(args)
        return urlparse.urlunparse(url_parts)

    def _do_login(self):
        if not hasattr(self, 'session'):
            self.session = requests.Session()
            self.session.verify = False
            self.session.get(self._get_backend_url('/admin/login.php'))
            self.session.post(
                self._get_backend_url('/admin/dologin.php'),
                data={'username': self.username, 'password': self.password},
                headers={'Content-Type': 'application/x-www-form-urlencoded'})

    def _get_token(self, html_text):
        match_string = 'type="hidden" name="token" value=\"(\w*)\"'
        token = re.findall(match_string, html_text)[0]
        return token

    def _extract_id(self, url, id_field='id'):
        q = urlparse.urlsplit(url).query
        return int(urlparse.parse_qs(q)[id_field][0])

    def request(self, action, resultset_path=None, **kwargs):
        data = {'action': action, 'responsetype': 'json'}
        data.update(kwargs)
        data.update({
            'password': hashlib.md5(self.password).hexdigest(),
            'username': self.username})

        req = self.Request(self.api_url, data, resultset_path=resultset_path)
        return req.data()

    def add_client(self, name=None, email=None, organization=None, **kwargs):
        data = self.request(
            'addclient',
            firstname=name,
            lastname='n/a',
            companyname=organization,
            email=email,
            address1='n/a',
            city='n/a',
            state='n/a',
            postcode='00000',
            country='OM',
            phonenumber='1234567',
            password2=pwgen(),
            currency=self.currency_code,
        )

        return data['clientid']

    def get_client_details(self, client_id):
        data = self.request('getclientsdetails', clientid=client_id)
        return {'balance': data.get('credit')}

    def get_invoices(self, client_id, with_pdf=False):
        invoices = self.request(
            'getinvoices',
            userid=client_id,
            resultset_path='invoices.invoice')

        for invoice in invoices:
            data = dict(
                backend_id=invoice['id'],
                date=self._parse_date(invoice['date']),
                amount=invoice['total'],
                status=invoice['status']
            )

            if with_pdf:
                data['pdf'] = self.get_invoice_pdf(invoice['id'])

            yield data

    def get_invoice_items(self, invoice_id):
        data = self.request('getinvoice', invoiceid=invoice_id)
        return [{'backend_id': item['id'],
                 'name': item['description'],
                 'type': item['type'],
                 'amount': item['amount']}
                for item in data['items']['item']]

    def get_invoice_pdf(self, invoice_id):
        self._do_login()

        pdf = self.session.get(self._get_backend_url('/dl.php', {'type': 'i', 'id': invoice_id}))
        return pdf.content

    def get_products(self):
        products = self.request('getproducts', resultset_path='products.product')
        for product in products:
            yield {'backend_id': product['pid'],
                   'price': product['pricing'][self.currency_name]['monthly'],
                   'description': product['description'] or '',
                   'name': product['name']}

    def create_invoice(self, items, payment_method='banktransfer'):
        response = self.request('createinvoice', paymentmethod=payment_method, **items)

        return response['invoiceid']

    def create_configurable_options_group(self, name, description, assigned_products_ids):
        self._do_login()

        # get unique token
        response = self.session.get(self._get_backend_url('admin/configproductoptions.php?action=managegroup'))
        token = self._get_token(response.text)

        response = self.session.post(
            self._get_backend_url('/admin/configproductoptions.php?action=savegroup&id='),
            data={
                'name': name,
                'description': description,
                'productlinks[]': assigned_products_ids,
                'token': token,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        return self._extract_id(response.url)

    def create_configurable_option(self, group_id, name, option_type='dropdown', option_values=None):
        """
            Create new configurable options in WHMCS of a defined option_type with option values and prices
            defined by the option_values dict. The prices are set to monthly prices of the configured
            currency.

            Example call:

                create_configurable_option(gid, 'flavor', option_values={'small': 1, 'big': 2})
                create_configurable_option(gid, 'support', option_type='yesno', option_values={'MO': 100})
        """
        self._do_login()
        response = self.session.get(
            self._get_backend_url('admin/configproductoptions.php?manageoptions=true&gid=%s' % group_id))
        token = self._get_token(response.text)

        # encoding from human to whmcs
        available_option_types = {
            'dropdown': 1,
            'radio': 2,
            'yesno': 3,
            'quantity': 4,
        }

        if option_values:
            component_id = ''  # cid during the first run, causes creation of a new group

            # first iteration is to create all the relevant flavors so that WHMCS would assign pk's to the ite,s
            for ov_name in option_values.keys():
                response = self.session.post(
                    self._get_backend_url(
                        '/admin/configproductoptions.php?manageoptions=true&cid=%s&gid=%s&save=true' %
                        (component_id, group_id)),
                    data={
                        'configoptionname': name,
                        'configoptiontype': available_option_types[option_type],
                        'token': token,
                        'addoptionname': ov_name
                    },
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                component_id = self._extract_id(response.url, id_field='cid')
                token = self._get_token(response.text)

            # second iteration to set prices of the option values
            response = self.session.get(
                self._get_backend_url(
                    '/admin/configproductoptions.php?manageoptions=true&cid=%s&gid=%s' %
                    (component_id, group_id)
                )
            )
            # get all the whmcs ids of configuration options
            exp = r'<input type="text" name="optionname\[(\d*)\]" value="(\w*)"'
            options = re.findall(exp, response.text)

            #
            prepared_price_data = {}
            for option in options:
                pk, option_name = option
                prepared_price_data['optionname[%s]' % pk] = option_name
                price = 0
                if option_name in option_values:
                    price = option_values[option_name]
                prepared_price_data['price[%s][%s][6]' % (self.currency_code, pk)] = price  # '6' corresponds to the monthly price

            token = self._get_token(response.text)
            prepared_price_data.update({
                'configoptionname': name,
                'configoptiontype': available_option_types[option_type],
                'token': token,
                'addoptionname': ''
            })

            # update options with prices
            self.session.post(
                self._get_backend_url(
                    '/admin/configproductoptions.php?manageoptions=true&cid=%s&gid=%s&save=true' %
                    (component_id, group_id)),
                data=prepared_price_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )

        return component_id

    def create_server_product(self, product_name, product_group_id=1):
        data = self.request(
            'addproduct',
            name=product_name,
            gid=product_group_id,
            type='server',
            paytype='recurring',
        )

        return data.get('pid')

