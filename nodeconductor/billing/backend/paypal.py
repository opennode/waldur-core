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
