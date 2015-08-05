import re
import urllib
import hashlib
import datetime
import urlparse
import requests
import logging
import lxml.html

from django.utils import six
from django.utils.http import urlsafe_base64_encode

from nodeconductor.billing.backend import BillingBackendError
from nodeconductor.billing.phpserialize import dumps as php_dumps
from nodeconductor.billing.models import PriceList
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

            try:
                data = response.json()
            except ValueError:  # JSONDecodeError
                raise BillingBackendError(
                    "Incorrect response from WHMCS backend %s" % self.url)

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
        if not hasattr(self, 'session'):
            self.session = requests.Session()
            self.session.verify = False
            self.session.get(self._get_backend_url('/admin/login.php'))
            self.session.post(
                self._get_backend_url('/admin/dologin.php'),
                data={'username': self.username, 'password': self.password},
                headers={'Content-Type': 'application/x-www-form-urlencoded'})

        pdf = self.session.get(self._get_backend_url('/dl.php', {'type': 'i', 'id': invoice_id}))
        return pdf.content

    def get_products(self):
        products = self.request('getproducts', resultset_path='products.product')
        for product in products:
            yield {'backend_id': product['pid'],
                   'price': product['pricing'][self.currency_name]['monthly'],
                   'description': product['description'] or '',
                   'options': self.get_product_configurable_options(product['pid']),
                   'name': product['name']}

    def get_product_configurable_options(self, product_id):
        # TODO: use _do_login()
        self.session = requests.Session()
        self.session.verify = False
        self.session.get(self._get_backend_url('/admin/login.php'))
        self.session.post(
            self._get_backend_url('/admin/dologin.php'),
            data={'username': self.username, 'password': self.password},
            headers={'Content-Type': 'application/x-www-form-urlencoded'})

        def get_page(url, *opts):
            response = self.session.get(self._get_backend_url('admin/' + url % opts))
            parser = lxml.html.HTMLParser(encoding=response.encoding)
            tree = lxml.html.fromstring(response.content, parser=parser)
            return tree

        def extract_id(text):
            return re.search(r'\w+\[(\d+)\]', text).group(1)

        tree = get_page('configproducts.php?action=edit&id=%s', product_id)
        cid = tree.find('.//select[@name="configoptionlinks[]"]/option[@selected]')

        if cid is None:
            logger.warning("Can't find configurable options for product #%s" % product_id)
            return {}

        options = {}
        tree = get_page('configproductoptions.php?action=managegroup&id=%s', cid.get('value'))
        for tr in tree.findall('.//table[@class="datatable"]/tr'):
            td = tr.find('td')
            if td is not None:
                opt_name = td.text.strip()
                opt_id = extract_id(tr.find('.//input').name)
                options[opt_name] = {'id': opt_id}

                tree = get_page('configproductoptions.php?manageoptions=true&cid=%s', opt_id)
                opt_type = tree.find('.//select[@name="configoptiontype"]/option[@selected]').get('value')

                if opt_type == '1':  # dropdown
                    options[opt_name]['choices'] = {
                        o.get('value'): extract_id(o.name) for o in
                        tree.xpath('.//input[starts-with(@name, "optionname")]')}

        return options

    def create_invoice(self, items, payment_method='banktransfer'):
        response = self.request('createinvoice', paymentmethod=payment_method, **items)

        return response['invoiceid']

    def _prepare_configurable_options(self, options, template=()):
        if not template:
            return options

        new_options = {}
        for opt in options:
            if opt not in template:
                raise BillingBackendError("Unknown configurable option '%s'" % opt)

            opt_id = template[opt]['id']
            opt_val = options[opt]
            choices = template[opt].get('choices', {})
            if choices:
                if opt_val not in choices:
                    raise BillingBackendError(
                        "Unknown configurable option value '%s:%s'" % (opt, opt_val))
                else:
                    opt_val = choices[opt_val]

            if isinstance(opt_val, bool):
                opt_val = int(opt_val)

            new_options[opt_id] = opt_val

        return new_options

    def add_order(self, product_name, client_id, **options):
        try:
            product = PriceList.objects.get(name=product_name)
        except PriceList.DoesNotExist as e:
            six.reraise(BillingBackendError, e)

        options = self._prepare_configurable_options(options, template=product.options)
        data = self.request(
            'addorder',
            pid=product.backend_id,
            clientid=client_id,
            configoptions=urlsafe_base64_encode(php_dumps(options)),
            billingcycle='monthly',
            paymentmethod='banktransfer',
        )

        return data['orderid']

    def update_order(self, order_id, client_id, **options):
        backend_products = self.request(
            'getclientsproducts',
            clientid=client_id,
            resultset_path='products.product')
        backend_product = next(p for p in backend_products if p['orderid'] == str(order_id))

        try:
            product = PriceList.objects.get(backend_id=backend_product['pid'])
        except PriceList.DoesNotExist as e:
            six.reraise(BillingBackendError, e)

        options = {'configoptions[%s]' % k: v for k, v in
                   self._prepare_configurable_options(options, template=product.options).items()}

        data = self.request(
            'upgradeproduct',
            serviceid=backend_product['id'],
            clientid=client_id,
            type='configoptions',
            paymentmethod='banktransfer',
            **options
        )

        self.accept_order(data['orderid'])

        return data['orderid']

    def accept_order(self, order_id):
        self.request('acceptorder', orderid=order_id)

    def cancel_order(self, order_id):
        self.request('cancelorder', orderid=order_id)

    def delete_order(self, order_id):
        self.request('deleteorder', orderid=order_id)
