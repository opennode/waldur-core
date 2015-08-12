import datetime
from decimal import Decimal
import hashlib
import logging
import lxml.html
import re
import requests
import urllib
import urlparse

from django.utils.http import urlsafe_base64_encode

from nodeconductor.cost_tracking import CostConstants
from nodeconductor.cost_tracking.models import DefaultPriceListItem
from nodeconductor.billing.backend import BillingBackendError
from nodeconductor.billing.phpserialize import dumps as php_dumps
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
                   'options': self.get_product_configurable_options(product['pid']),
                   'name': product['name']}

    def get_client_products(self, client_id):
        products = self.request(
            'getclientsproducts', clentid=client_id, limitnum=1000, resultset_path='products.product')
        for product in products:
            print product
            yield {
                'id': product['id'],
                'backend_id': product['pid'],
                'name': product['name'],
                'hostname': product['domain'],
            }

    def get_client_orders(self, client_id):
        """ Get all orders for given client """
        whmcs_orders = self.request('getorders', userid=client_id, limitnum=1000, resultset_path='orders.order')
        client_products = list(self.get_client_products(client_id))
        for whmcs_order in whmcs_orders:
            yield self._format_whmcs_order(whmcs_order, client_products)

    def _format_whmcs_order(self, whmcs_order, client_products):
        """ Take significant data from whmcs_order """
        whmcs_items = whmcs_order.get('lineitems', {}).get('lineitem', [])
        currency = whmcs_order['currencysuffix']
        items = []

        for whmcs_item in whmcs_items:
            # sometimes WHMCS return amount as <amount><currency> (Ex.: 15.00OMR), we need to handle  this case
            if whmcs_item['amount'].endswith(currency):
                whmcs_amount = whmcs_item['amount'][:-len(currency)]
            else:
                whmcs_amount = whmcs_item['amount']

            try:
                product_scope = [cp for cp in client_products if cp['id'] == whmcs_item['relid']][0]
            except IndexError:
                product_scope = ''

            items.append({
                'amount': Decimal(whmcs_amount),
                'product': re.compile(r'<[^>]+>').sub('', whmcs_item['product']),  # remove tags from product name
                'status': whmcs_item['status'],
                'product_type': self._get_product_type_name(whmcs_item['producttype']),
                'product_scope': product_scope,
            })

        return {
            'date': datetime.datetime.strptime(whmcs_order['date'], '%Y-%m-%d %H:%M:%S'),
            'amount': Decimal(whmcs_order['amount']),
            'currency': currency,
            'id': whmcs_order['id'],
            'status': self._get_status_name(whmcs_order['status']),
            'payment_status': whmcs_order['paymentstatus'],
            'items': items,
            'number': whmcs_order['ordernum'],
        }

    def _get_product_type_name(self, whmcs_product_type):
        product_type_map = {
            'Upgrade': 'Modification',
            'Dedicated/VPS Server': 'Virtual machine',
        }
        try:
            return product_type_map[whmcs_product_type]
        except KeyError:
            return whmcs_product_type

    def _get_status_name(self, whmcs_status):
        status_map = {
            'Active': 'Completed',
        }
        try:
            return status_map[whmcs_status]
        except KeyError:
            return whmcs_status

    def get_product_configurable_options(self, product_id):
        self._do_login()

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

    def add_order(self, resource_content_type, client_id, name='', **options):
        # Fetch *any* item of specific content type to get backend id
        product = DefaultPriceListItem.objects.filter(
            resource_content_type=resource_content_type).first()
        template = DefaultPriceListItem.get_options(resource_content_type=resource_content_type)
        options = self._prepare_configurable_options(options, template=template)

        if not product:
            raise BillingBackendError(
                "Product '%s' is missing on backend" % resource_content_type)

        data = self.request(
            'addorder',
            pid=product.backend_product_id,
            domain=name,
            clientid=client_id,
            configoptions=urlsafe_base64_encode(php_dumps(options)),
            billingcycle='monthly',
            paymentmethod='banktransfer',
            noinvoice=True,
            noemail=True,
        )
        logger.info('WHMCS order was added with id %s', data['orderid'])
        return data['orderid'], data['productids'], product.backend_product_id

    def update_order(self, client_id, backend_resource_id, backend_template_id, **options):
        template = DefaultPriceListItem.get_options(backend_product_id=backend_template_id)
        options = {'configoptions[%s]' % k: v for k, v in
                   self._prepare_configurable_options(options, template=template).items()}

        data = self.request(
            'upgradeproduct',
            serviceid=backend_resource_id,
            clientid=client_id,
            type='configoptions',
            paymentmethod='banktransfer',
            **options
        )

        self.accept_order(data['orderid'])
        logger.info('WHMCS update order was added with id %s', data['orderid'])

    def accept_order(self, order_id):
        self.request('acceptorder', orderid=order_id)

    def cancel_order(self, order_id):
        self.request('cancelorder', orderid=order_id)

    def cancel_purchase(self, backend_resource_id):
        self.request(
            'addcancelrequest',
            serviceid=backend_resource_id,
            type='Immediate',
            reason='VM deletion',
        )

    def delete_order(self, order_id):
        self.request('deleteorder', orderid=order_id)

    def _create_configurable_options_group(self, name, description="", assigned_products_ids=None):
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

    def _create_configurable_options(self, group_id, name, option_type='dropdown', option_values=None):
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
            exp = r'<input type="text" name="optionname\[(\d*)\]" value="([\w\.\-\_ ]*)"'
            options = re.findall(exp, response.text)

            prepared_price_data = {}
            for option in options:
                pk, option_name = option
                prepared_price_data['optionname[%s]' % pk] = option_name
                price = 0
                if option_name in option_values:
                    price = option_values[option_name]
                # convert price to a string
                price = float(price)
                # NB! If currency_code is set incorrect, WHMCS will silently fail to update prices
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

    def propagate_pricelist(self, resource_content_type):
        # TODO: Refactor it:
        #       -- it's impossible to update product's configuration right now
        #       -- there's overhead in fetching option's IDs (could be fetched right after creating)

        # 1. create a product of a particular type
        product_name = "{}-{}".format(resource_content_type.app_label, resource_content_type.model)
        for product in self.request('getproducts', resultset_path='products.product'):
            if product_name == product['name']:
                raise BillingBackendError("Product %s already exists on backend" % product_name)

        response = self.request(
            'addproduct',
            name=product_name,
            gid=1,
            type='server',
            paytype='recurring',
            module='autorelease',
        )

        pid = response['pid']

        # 2. define configuration options
        type_mapping = {
            CostConstants.PriceItem.FLAVOR: 'dropdown',
            CostConstants.PriceItem.STORAGE: 'quantity',
            CostConstants.PriceItem.SUPPORT: 'dropdown',
            CostConstants.PriceItem.LICENSE_OS: 'dropdown',
            CostConstants.PriceItem.LICENSE_APPLICATION: 'dropdown',
        }

        gid = self._create_configurable_options_group(
            "Configuration of %s" % product_name, assigned_products_ids=[pid])

        # 3. create configuration based on pricelist
        for pricelist_item_type in type_mapping.keys():
            pricelist_items = DefaultPriceListItem.objects.filter(
                resource_content_type=resource_content_type,
                item_type=pricelist_item_type)

            self._create_configurable_options(
                gid, pricelist_item_type,
                option_type=type_mapping[pricelist_item_type],
                option_values={i.key: i.value for i in pricelist_items})

        # 4. pull-up created configuration back to NC
        options = self.get_product_configurable_options(pid)
        pricelist_items = DefaultPriceListItem.objects.filter(
            resource_content_type=resource_content_type)

        for item in pricelist_items:
            option = options[item.item_type]
            if 'choices' in option:
                item.backend_choice_id = option['choices'][item.key]

            item.backend_option_id = option['id']
            item.backend_product_id = pid
            item.save()

    def get_total_cost_of_active_products(self, client_id):
        products = self.request('getclientsproducts', clientid=client_id, resultset_path='products.product')
        costs = [float(product['recurringamount']) for product in products if product['status'] == 'Active']
        return sum(costs)
