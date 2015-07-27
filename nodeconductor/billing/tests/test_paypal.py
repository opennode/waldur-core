import decimal
import mock

from django.test.utils import override_settings
from rest_framework import test, status
from rest_framework.reverse import reverse

from nodeconductor.billing import models as billing_models
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


@override_settings(NODECONDUCTOR={
    'BILLING': {
        'backend': 'nodeconductor.billing.backend.paypal.PaypalBackend',
        'mode': 'sandbox',
        'client_id': '',
        'client_secret': '',
        'currency_name': 'USD',
        'return_url': 'http://example.com/payment/return',
    }
})
class PaypalPaymentTest(test.APISimpleTestCase):

    def setUp(self):
        self.customer = structure_factories.CustomerFactory(balance=0)
        self.owner = structure_factories.UserFactory()
        self.other = structure_factories.UserFactory()
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)

        self.url = reverse('payment-list')

        self.request_data = {
            'amount': decimal.Decimal('9.99'),
            'customer': structure_factories.CustomerFactory.get_url(self.customer),
        }

        self.response_data = {
            'amount': self.request_data['amount'],
            'approval_url': 'https://www.sandbox.paypal.com/webscr?cmd=_express-checkout&token=EC-60U79048BN7719609',
            'payment_id': 'PAY-6RV70583SB702805EKEYSZ6Y',
            'payer_id': '7E7MGXCWTTKK2',
            'create_ok': True,
            'execute_ok': True,
            'error_message': '',
        }

        self.mock = self.paypal_payment_factory()

    def tearDown(self):
        billing_models.Payment.objects.all().delete()

    def paypal_payment_factory(self):
        params = self.response_data

        class Link(object):
            rel = 'approval_url'
            href = params['approval_url']

        class Payment(object):
            id = params['payment_id']
            links = [Link]
            error = params['error_message']

            def __init__(self, data=None):
                pass

            def create(self):
                return params['create_ok']

            def execute(self, data):
                return params['execute_ok']

            @classmethod
            def find(self, payment_id):
                return Payment()

        return Payment

    def create_payment(self, user):
        with mock.patch('paypalrestsdk.Payment', self.mock):
            self.client.force_authenticate(user)
            return self.client.post(self.url, data=self.request_data)

    def approve_payment(self, user):
        with mock.patch('paypalrestsdk.Payment', self.mock):
            payment = billing_models.Payment.objects.create(
                customer=self.customer,
                amount=self.request_data['amount'],
                backend_id=self.response_data['payment_id'],
            )

            self.client.force_authenticate(user)
            base_url = reverse('payment-detail', kwargs={'uuid': payment.uuid.hex})
            url = base_url + 'approve/?paymentId=%s&PayerID=%s' % (
                self.response_data['payment_id'], self.response_data['payer_id'])
            return self.client.get(url)

    def cancel_payment(self, user):
        with mock.patch('paypalrestsdk.Payment', self.mock):
            payment = billing_models.Payment.objects.create(
                customer=self.customer,
                amount=self.request_data['amount'],
                backend_id=self.response_data['payment_id'],
            )

            self.client.force_authenticate(user)
            url = reverse('payment-detail', kwargs={'uuid': payment.uuid.hex}) + 'cancel/'
            return self.client.get(url)

    def test_user_can_not_create_payment_for_other_customer(self):
        response = self.create_payment(self.other)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_can_create_payment_for_owned_customer(self):
        response = self.create_payment(self.owner)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_staff_can_create_payment_for_any_customer(self):
        response = self.create_payment(self.staff)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_when_payment_created_correct_database_object_created(self):
        response = self.create_payment(self.owner)

        self.assertEqual(response.data['approval_url'], self.response_data['approval_url'])

        payment = billing_models.Payment.objects.get(backend_id=self.response_data['payment_id'])
        self.assertEqual(payment.amount, self.request_data['amount'])

    def test_when_backend_fails_database_object_not_created(self):
        self.response_data['create_ok'] = False

        response = self.create_payment(self.owner)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertFalse(billing_models.Payment.objects.filter(
            backend_id=self.response_data['payment_id']).exists())

    def test_user_can_not_approve_payment_for_other_customer(self):
        response = self.approve_payment(self.other)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_can_approve_payment_for_owned_customer(self):
        response = self.approve_payment(self.owner)

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response['Location'], self.customer.get_billing_backend().api.return_url)

        customer = structure_models.Customer.objects.get(id=self.customer.id)
        self.assertEqual(customer.balance, self.customer.balance + self.request_data['amount'])

    def test_user_can_not_cancel_payment_for_other_customer(self):
        response = self.cancel_payment(self.other)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_can_cancel_payment_for_owned_customer(self):
        response = self.cancel_payment(self.owner)

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response['Location'], self.customer.get_billing_backend().api.return_url)

        customer = structure_models.Customer.objects.get(id=self.customer.id)
        self.assertEqual(customer.balance, self.customer.balance)
