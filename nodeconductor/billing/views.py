import logging

from django.conf import settings
import django_filters
from django_fsm import TransitionNotAllowed
from django.shortcuts import redirect
from django.utils import six
from django.views.static import serve
from rest_framework import mixins, viewsets, permissions, response, decorators, exceptions, status
from rest_framework.exceptions import APIException
from rest_framework.reverse import reverse

from nodeconductor.billing.backend import BillingBackendError
from nodeconductor.billing.log import event_logger
from nodeconductor.billing.models import PriceList, Invoice, Payment
from nodeconductor.billing.serializers import InvoiceSerializer, PaymentSerializer, PaymentApproveSerializer
from nodeconductor.core.filters import DjangoMappingFilterBackend
from nodeconductor.structure.filters import GenericRoleFilter
from nodeconductor.structure.models import CustomerRole


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
            items = backend.api.get_invoice_items(invoice.backend_id)
            return response.Response(items, status=status.HTTP_200_OK)
        except BillingBackendError:
            return response.Response(
                {'Detail': 'Cannot retrieve data from invoice backend'}, status=status.HTTP_400_BAD_REQUEST)


class CreateByStaffOrOwnerMixin(object):
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        customer = serializer.validated_data['customer']

        if not self.request.user.is_staff and not customer.has_user(self.request.user, CustomerRole.OWNER):
            raise exceptions.PermissionDenied()
        return super(CreateByStaffOrOwnerMixin, self).create(request)


class PaymentView(CreateByStaffOrOwnerMixin,
                  mixins.CreateModelMixin,
                  mixins.ListModelMixin,
                  mixins.RetrieveModelMixin,
                  viewsets.GenericViewSet):

    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    lookup_field = 'uuid'
    filter_backends = (GenericRoleFilter, )
    permission_classes = (
        permissions.IsAuthenticated,
        permissions.DjangoObjectPermissions,
    )

    def perform_create(self, serializer):
        """
        Create new payment via Paypal gateway
        """

        customer = serializer.validated_data['customer']
        payment = serializer.save()
        url = reverse('payment-detail', kwargs={'uuid': payment.uuid.hex}, request=self.request)

        try:
            backend = customer.get_billing_backend()

            backend_payment = backend.api.make_payment(
                amount=serializer.validated_data['amount'],
                description='Replenish account in NodeConductor for %s' % customer.name,
                return_url=url + 'approve/',
                cancel_url=url + 'cancel/')

            payment.backend_id = backend_payment.payment_id
            payment.approval_url = backend_payment.approval_url
            payment.set_created()
            payment.save()

            event_logger.payment.info(
                'Created new payment for {customer_name}',
                event_type='payment_creation_succeeded',
                event_context={'payment': payment}
            )

        except BillingBackendError as e:
            logging.warning('Unable to create payment because of backend error %s', e)
            payment.set_erred()
            payment.save()
            raise APIException()

    @decorators.detail_route()
    def approve(self, request, uuid):
        """
        Callback view for Paypal payment approval.
        Do not use it directly. It is internal API.
        """
        payment = self.get_object()

        serializer = PaymentApproveSerializer(instance=payment, data={
            'payment_id': request.query_params.get('paymentId'),
            'payer_id': request.query_params.get('PayerID')
        })
        serializer.is_valid(raise_exception=True)

        payment_id = serializer.validated_data['payment_id']
        payer_id = serializer.validated_data['payer_id']

        backend = payment.customer.get_billing_backend()

        try:
            backend.api.approve_payment(payment_id, payer_id)

            payment.customer.credit_account(payment.amount)
            payment.set_approved()
            payment.save()

            event_logger.payment.info(
                'Payment for {customer_name} has been approved',
                event_type='payment_approval_succeeded',
                event_context={'payment': payment}
            )
            return redirect(backend.api.return_url)

        # Do not raise error
        except BillingBackendError as e:
            logging.warning('Unable to approve payment because of backend error %s', e)
            payment.set_erred()
            payment.save()
            return redirect(backend.api.return_url)

        except TransitionNotAllowed:
            logging.warning('Unable to approve payment because of invalid state')
            payment.set_erred()
            payment.save()
            return redirect(backend.api.return_url)

    @decorators.detail_route()
    def cancel(self, request, uuid):
        """
        Callback view for Paypal payment cancel.
        Do not use it directly. It is internal API.
        """
        payment = self.get_object()
        backend = payment.customer.get_billing_backend()
        try:
            payment.set_cancelled()
            payment.save()

            event_logger.payment.info(
                'Payment for {customer_name} has been cancelled',
                event_type='payment_cancel_succeeded',
                event_context={'payment': payment}
            )
            return redirect(backend.api.return_url)

        # Do not raise error
        except TransitionNotAllowed:
            logging.warning('Unable to cancel payment because of invalid state')
            return redirect(backend.api.return_url)
