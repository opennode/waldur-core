import re
import requests
import logging

from datetime import datetime
from lxml.html.clean import Cleaner
from lxml.builder import E, ElementMaker
from lxml import etree

from django.contrib.contenttypes.models import ContentType

from nodeconductor.cost_tracking.models import DefaultPriceListItem
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

    def propagate_pricelist(self):
        # Generate catalog and push it to backend
        # http://killbill.github.io/killbill-docs/0.15/userguide_subscription.html#components-catalog

        plans = E.plans()
        prods = E.products()
        plannames = []

        nc_name = lambda name: re.sub(r'[\s:;,+%&$@/]+', '', name)

        priceitems = DefaultPriceListItem.objects.values_list('resource_content_type', flat=True).distinct()
        for cid in priceitems:
            content_type = ContentType.objects.get_for_id(cid)
            plan_name = "{}-{}".format(content_type.app_label, content_type.model)
            product_name = nc_name(plan_name.title().replace('-', ''))

            usages = E.usages()
            for priceitem in DefaultPriceListItem.objects.filter(resource_content_type=cid):
                usage = E.usage(
                    E.billingPeriod('MONTHLY'),
                    E.tiers(E.tier(E.blocks(E.tieredBlock(
                        E.unit('hours'),
                        E.size('1'),
                        E.prices(E.price(
                            E.currency('USD'),
                            E.value(str(priceitem.value)),
                        )),
                        E.max('744'),  # max hours in a month
                    )))),
                    name=nc_name("{}-{}".format(priceitem.item_type, priceitem.key)),
                    billingMode='IN_ARREAR',
                    usageType='CONSUMABLE')
                usages.append(usage)

            plan = E.plan(
                E.product(product_name),
                E.finalPhase(
                    E.duration(E.unit('UNLIMITED')),
                    usages,
                    type='EVERGREEN'),
                name=plan_name)

            prods.append(E.product(E.category('STANDALONE'), name=product_name))

            plans.append(plan)
            plannames.append(plan_name)

        EC = ElementMaker(nsmap={'xsi': 'http://www.w3.org/2001/XMLSchema-instance'})
        catalog = EC.catalog(
            E.effectiveDate(datetime.utcnow().isoformat("T")),
            E.catalogName('NodeConductor'),
            E.recurringBillingMode('IN_ADVANCE'),
            E.currencies(E.currency('USD')),
            E.units(E.unit(name='hours')),
            prods,
            E.rules(E.priceList(E.priceListCase(E.toPriceList('DEFAULT')))),
            plans,
            E.priceLists(E.defaultPriceList(E.plans(*[E.plan(n) for n in plannames]), name='DEFAULT')),
            **{'{http://www.w3.org/2001/XMLSchema-instance}schemaLocation': 'CatalogSchema.xsd'})

        xml = etree.tostring(
            catalog, xml_declaration=True, pretty_print=True, standalone=False, encoding='UTF-8')

        self.catalog.post(xml)


class KillBill(object):

    class BaseResource(object):
        path = NotImplemented
        type = 'application/json'

        def __init__(self, credentials):
            self.__dict__ = credentials

        def __repr__(self):
            return self.api_url + self.path

        def get(self):
            return self.request(self.path, method='GET')

        def post(self, data):
            return self.request(self.path, method='POST', data=data)

        def request(self, url, method='GET', data=None, **kwargs):
            response_types = {'application/json': 'json', 'application/xml': 'xml'}
            headers = {'User-Agent': 'NodeConductor/%s' % __version__,
                       'Accept': 'application/json',
                       'X-Killbill-ApiKey': self.api_key,
                       'X-Killbill-ApiSecret': self.api_secret}

            if method.upper() == 'POST':
                headers['Content-Type'] = self.type
                headers['X-Killbill-CreatedBy'] = 'NodeConductor'

            response = getattr(requests, method.lower())(
                self.api_url + url, data=data, auth=self.auth, headers=headers)

            response_type = response_types.get(response.headers.get('content-type'), '')
            if response.status_code not in (200, 201):
                reason = response.reason
                if response_type == 'json':
                    try:
                        reason = response.json()['message']
                    except ValueError:
                        pass
                elif response.status_code == 500:
                    try:
                        txt = etree.fromstring(response.text)
                        reason = txt.xpath('.//pre/text()')[1].split('\n')[:5][2]
                    except ValueError:
                        pass

                raise BillingBackendError(
                    "%s. Request to Killbill backend failed: %s" % (response.status_code, reason))

            try:
                if response_type == 'xml':
                    data = etree.fromstring(
                        response.text.encode('utf-8'),
                        etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8'))

                elif response_type == 'json':
                    data = response.json()

                else:
                    data = response.text

            except ValueError as e:
                raise BillingBackendError(
                    "Incorrect response from Killbill backend %s: e" % (self.url, e))

            return data

    class Catalog(BaseResource):
        path = 'catalog'
        type = 'application/xml'

    class Invoice(BaseResource):
        path = 'invoices'

    class Test(BaseResource):
        path = 'test/clock'
