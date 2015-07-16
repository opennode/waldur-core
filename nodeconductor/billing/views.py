import logging

from django.conf import settings
from django.db import transaction, IntegrityError, DatabaseError
import django_filters
from django_fsm import TransitionNotAllowed
from django.shortcuts import redirect
from django.utils import six
from django.views.static import serve
import paypalrestsdk as paypal
from rest_framework import mixins, viewsets, permissions, response, decorators, exceptions, status
from rest_framework.reverse import reverse

from nodeconductor.billing.backend import BillingBackendError
from nodeconductor.billing.log import event_logger
from nodeconductor.billing.models import PriceList, Invoice, Payment
from nodeconductor.billing.serializers import InvoiceSerializer, PaymentSerializer, PaymentApproveSerializer
from nodeconductor.core.filters import DjangoMappingFilterBackend
from nodeconductor.structure.filters import GenericRoleFilter
from nodeconductor.structure.models import CustomerRole


paypal.configure({
    'mode': settings.NODECONDUCTOR['PAYPAL']['mode'],
    'client_id': settings.NODECONDUCTOR['PAYPAL']['client_id'],
    'client_secret': settings.NODECONDUCTOR['PAYPAL']['client_secret'],
})


class PaypalException(Exception):
    pass


class BillingViewSet(viewsets.GenericViewSet):

    @decorators.list_route()
    def pricelist(self, request):
        return response.Response({pl.name: pl.price for pl in PriceList.objects.all()})


class InvoiceFilter(django_filters.FilterSet):
    customer = django_filters.CharFilter(name='customer__uuid', distinct=True)
    customer_name = django_filters.CharFilter(
        name='customer__name',
        lookup_type='icontains',
        distinct=True
    )
    customer_native_name = django_filters.CharFilter(
        name='customer__native_name',
        lookup_type='icontains',
        distinct=True
    )
    customer_abbreviation = django_filters.CharFilter(
        name='customer__abbreviation',
        lookup_type='icontains',
        distinct=True
    )
    month = django_filters.CharFilter(name='date', lookup_type='month')
    year = django_filters.CharFilter(name='date', lookup_type='year')

    class Meta(object):
        model = Invoice
        fields = [
            'customer', 'customer_name', 'customer_native_name', 'customer_abbreviation',
            'year', 'month',
            'amount',
            'status',
            'date',
        ]
        order_by = [
            'date',
            '-date',
            'amount',
            '-amount',
            'status',
            '-status',
            'customer__name',
            '-customer__name',
            'customer__abbreviation',
            '-customer__abbreviation',
            'customer__native_name',
            '-customer__native_name',
        ]
        order_by_mapping = {
            # Proper field naming
            'customer_name': 'customer__name',
            'customer_abbreviation': 'customer__abbreviation',
            'customer_native_name': 'customer__native_name',
        }


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Invoice.objects.all()
    filter_class = InvoiceFilter
    filter_backends = (GenericRoleFilter, DjangoMappingFilterBackend)
    lookup_field = 'uuid'
    permission_classes = (
        permissions.IsAuthenticated,
        permissions.DjangoObjectPermissions,
    )
    serializer_class = InvoiceSerializer

    @decorators.detail_route()
    def pdf(self, request, uuid=None):
        invoice = self.get_object()
        if not invoice.pdf:
            raise exceptions.NotFound("There's no PDF for this invoice")

        response = serve(request, invoice.pdf.name, document_root=settings.MEDIA_ROOT)
        if request.query_params.get('download'):
            response['Content-Type'] = 'application/pdf'
            response['Content-Disposition'] = 'attachment; filename="invoice.pdf"'

        return response

    @decorators.detail_route()
    def usage_pdf(self, request, uuid=None):
        invoice = self.get_object()
        if not invoice.usage_pdf:
            raise exceptions.NotFound("There's no usage PDF for this invoice")

        response = serve(request, invoice.usage_pdf.name, document_root=settings.MEDIA_ROOT)
        if request.query_params.get('download'):
            response['Content-Type'] = 'application/pdf'
            response['Content-Disposition'] = 'attachment; filename="usage.pdf"'

        return response

    @decorators.detail_route()
    def items(self, request, uuid=None):
        invoice = self.get_object()
        # TODO: Move it to createsampleinvoices
        if not invoice.backend_id:
            # Dummy items
            items = [
                {
                    "amount": "7.95",
                    "type": "Hosting",
                    "name": "Home Package - topcorp.tv (02/10/2014 - 01/11/2014)"
                }
            ]
            return response.Response(items, status=status.HTTP_200_OK)
        try:
            backend = invoice.customer.get_billing_backend()
            items = backend.get_invoice_items(invoice.backend_id)
            return response.Response(items, status=status.HTTP_200_OK)
        except BillingBackendError:
            return response.Response(
                {'Detail': 'Cannot retrieve data from invoice backend'}, status=status.HTTP_400_BAD_REQUEST)


class PaymentView(mixins.ListModelMixin,
                  mixins.RetrieveModelMixin,
                  viewsets.GenericViewSet):

    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    lookup_field = 'uuid'
    filter_backends = (GenericRoleFilter, )

    def create(self, request):
        """
        Create new payment via Paypal gateway
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        customer = serializer.validated_data['customer']
        amount = serializer.validated_data['amount']

        # DjangoObjectPermissions is not used because it cannot enforce
        # create permissions based on the body of the request.
        if not self.request.user.is_staff and not customer.has_user(self.request.user, CustomerRole.OWNER):
            raise exceptions.PermissionDenied()

        try:
            with transaction.atomic():
                payment_object = Payment.objects.create(
                    customer=customer,
                    amount=amount,
                    success_url=serializer.validated_data['success_url'],
                    error_url=serializer.validated_data['error_url'])

                payment_url = reverse(
                    'payment-detail',
                    kwargs={'uuid': payment_object.uuid},
                    request=self.request)

                payment = paypal.Payment({
                    'intent': 'sale',
                    'payer': {'payment_method': 'paypal'},
                    'transactions': [
                        {
                            'amount': {
                                'total': str(amount), # serialize decimal
                                'currency': settings.NODECONDUCTOR['PAYPAL']['currency_name']
                            },
                            'description': 'Replenish account in NodeConductor for %s' % customer.name
                        }
                    ],
                    'redirect_urls': {
                        'return_url': payment_url + 'approve/',
                        'cancel_url': payment_url + 'cancel/'
                    }
                })

                try:
                    if not payment.create():
                        # Rollback transaction by raising exception
                        raise PaypalException(payment.error)
                except paypal.exceptions.ConnectionError as e:
                    six.reraise(PaypalException, e)

                payment_object.backend_id = payment.id
                payment_object.save()

                event_logger.payment.info(
                    'Created new payment for {customer_name}',
                    event_type='payment_creation_succeeded',
                    event_context={'payment': payment_object}
                )

                for link in payment.links:
                    if link.rel == 'approval_url':
                        approval_url = link.href
                        return response.Response({'approval_url': approval_url}, status=status.HTTP_201_CREATED)

        except PaypalException as e:
            logging.warning('Unable to create payment because of backend error %s', e)
            return response.Response({'detail': 'Unable to create payment because of backend error'},
                                     status=status.HTTP_400_BAD_REQUEST)

    @decorators.detail_route()
    def approve(self, request, uuid):
        """
        Callback view for Paypal payment approval
        """
        db_payment = self.get_object()

        serializer = PaymentApproveSerializer(instance=db_payment, data={
            'payment_id': request.query_params.get('paymentId'),
            'payer_id': request.query_params.get('PayerID')
        })
        serializer.is_valid(raise_exception=True)

        payment_id = serializer.validated_data['payment_id']
        payer_id = serializer.validated_data['payer_id']

        try:
            payment = paypal.Payment.find(payment_id)
        except paypal.exceptions.ResourceNotFound:
            raise exceptions.NotFound()

        try:
            with transaction.atomic():
                db_payment.approve()
                db_payment.save()
                db_payment.customer.credit_account(db_payment.amount)

                try:
                    if not payment.execute({'payer_id': payer_id}):
                        # Rollback transaction by raising exception
                        raise PaypalException(payment.error)
                except paypal.exceptions.ConnectionError as e:
                    six.reraise(PaypalException, e)

                event_logger.payment.info(
                    'Payment for {customer_name} has been approved',
                    event_type='payment_approval_succeeded',
                    event_context={'payment': db_payment}
                )
                return redirect(db_payment.success_url)

        except PaypalException as e:
            logging.warning('Unable to approve payment because of backend error %s', e)
            return redirect(db_payment.error_url)

        except TransitionNotAllowed:
            logging.warning('Unable to approve payment because of invalid state')
            return redirect(db_payment.error_url)

    @decorators.detail_route()
    def cancel(self, request, uuid):
        """
        Callback view for Paypal payment cancel
        """
        payment = self.get_object()
        try:
            with transaction.atomic():
                payment.cancel()
                payment.save()

                event_logger.payment.info(
                    'Payment for {customer_name} has been cancelled',
                    event_type='payment_cancel_succeeded',
                    event_context={'payment': payment}
                )
                return redirect(payment.error_url)

        except TransitionNotAllowed:
            logging.warning('Unable to cancel payment because of invalid state')
            return redirect(payment.error_url)
