import datetime
import decimal
import urlparse

import dateutil.parser
from django.utils import six
import paypalrestsdk as paypal

from nodeconductor.billing.backend import BillingBackendError


class PaypalPayment(object):
    def __init__(self, payment_id, approval_url):
        self.payment_id = payment_id
        self.approval_url = approval_url


class PaypalBackend(object):
    def __init__(self, mode, client_id, client_secret, return_url, currency_name, **kwargs):
        self.return_url = return_url
        self.currency_name = currency_name

        paypal.configure({
            'mode': mode,
            'client_id': client_id,
            'client_secret': client_secret
        })

    def make_payment(self, amount, description, return_url, cancel_url):
        payment = paypal.Payment({
            'intent': 'sale',
            'payer': {'payment_method': 'paypal'},
            'transactions': [
                {
                    'amount': {
                        'total': str(amount), # serialize decimal
                        'currency': self.currency_name
                    },
                    'description': description
                }
            ],
            'redirect_urls': {
                'return_url': return_url,
                'cancel_url': cancel_url
            }
        })

        try:
            if payment.create():
                for link in payment.links:
                    if link.rel == 'approval_url':
                        approval_url = link.href
                        return PaypalPayment(payment.id, approval_url)
            else:
                raise BillingBackendError(payment.error)
        except paypal.exceptions.ConnectionError as e:
            six.reraise(BillingBackendError, e)

    def approve_payment(self, payment_id, payer_id):
        try:
            payment = paypal.Payment.find(payment_id)
            if payment.execute({'payer_id': payer_id}):
                return True
            else:
                raise BillingBackendError(payment.error)
        except paypal.exceptions.ConnectionError as e:
            six.reraise(BillingBackendError, e)

    def create_plan(self, amount, name, description, return_url, cancel_url):
        """
        Create and activate montlhy billing plan using PayPal Rest API.
        On success returns plan_id
        """
        plan = paypal.BillingPlan({
            'name': name,
            'description': description,
            'type': 'INFINITE',
            'payment_definitions': [{
                'name': 'Monthly payment for {}'.format(name),
                'type': 'REGULAR',
                'frequency_interval': 1,
                'frequency': 'MONTH',
                'cycles': 0,
                'amount': {
                    'currency': self.currency_name,
                    'value': str(amount)
                }
            }],
            'merchant_preferences': {
                'return_url': return_url,
                'cancel_url': cancel_url,
                'auto_bill_amount': 'YES',
            }
        })

        try:
            if plan.create() and plan.activate():
                return plan.id
            else:
                raise BillingBackendError(plan.error)
        except paypal.exceptions.ConnectionError as e:
            six.reraise(BillingBackendError, e)

    def create_agreement(self, plan_id, name):
        """
        Create billing agreement. On success returns approval_url and token
        """
        # PayPal does not support immediate start of agreement
        # That's why we need to artifically increase start date by small amount of time
        start_date = datetime.datetime.utcnow() + datetime.timedelta(minutes=1)

        # PayPal does not fully support ISO 8601 format
        formatted_date = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')

        agreement = paypal.BillingAgreement({
            'name': name,
            'description': 'Agreement for {}'.format(name),
            'start_date': formatted_date,
            'payer': {'payment_method': 'paypal'},
            'plan': {'id': plan_id}
        })
        try:
            if agreement.create():
                for link in agreement.links:
                    if link.rel == 'approval_url':
                        approval_url = link.href

                        # PayPal does not return agreement ID until it is approved
                        # That's why we need to extract token in order to identify it with order in DB
                        parts = urlparse.urlparse(approval_url)
                        params = urlparse.parse_qs(parts.query)
                        token = params.get('token')
                        if not token:
                            raise BillingBackendError('Unable to parse token from approval_url')
                        return approval_url, token[0]
            else:
                raise BillingBackendError(agreement.error)
        except paypal.exceptions.ConnectionError as e:
            six.reraise(BillingBackendError, e)

    def execute_agreement(self, payment_token):
        """
        Agreement should be executed if user has approved it.
        On success returns agreement id
        """
        try:
            agreement = paypal.BillingAgreement.execute(payment_token)
            if not agreement:
                raise BillingBackendError('Agreement not found')
            return agreement.id
        except paypal.exceptions.ConnectionError as e:
            six.reraise(BillingBackendError, e)

    def cancel_agreement(self, agreement_id):
        try:
            agreement = BillingAgreement.find(agreement_id)
            if not agreement:
                raise BillingBackendError('Agreement not found')

            # Because user may cancel agreement via PayPal web UI
            # we need to distinguish it from cancel done via API
            if agreement.cancel({'note': 'Canceling the agreement by application'}):
                return True
            else:
                raise BillingBackendError(agreement.error)
        except paypal.exceptions.ConnectionError as e:
            six.reraise(BillingBackendError, e)

    def get_agreement_transactions(self, agreement_id, start_date, end_date):
        try:
            agreement = paypal.BillingAgreement.find(agreement_id)
            if not agreement:
                raise BillingBackendError('Agreement not found')

            # If start and end date are the same PayPal raises exceptions
            # That's why we need to increase end_date by one day
            end_date += datetime.timedelta(days=1)

            formatted_start_date = start_date.strftime('%Y-%m-%d')
            formatted_end_date = end_date.strftime('%Y-%m-%d')

            data = agreement.search_transactions(formatted_start_date, formatted_end_date)
            txs = data.agreement_transaction_list
            if not txs:
                return []
            results = []
            for tx in txs:
                if tx.status != 'Completed':
                    continue
                results.append({
                    'time_stamp': dateutil.parser.parse(tx.time_stamp),
                    'transaction_id': tx.transaction_id,
                    'amount': decimal.Decimal(tx.amount.value),
                    'payer_email': tx.payer_email
                })
            return results

        except paypal.exceptions.ConnectionError as e:
            six.reraise(BillingBackendError, e)
