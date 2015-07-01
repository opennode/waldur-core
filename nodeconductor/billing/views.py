import django_filters

from rest_framework import viewsets, permissions, response, decorators, exceptions, status

from django.conf import settings
from django.views.static import serve
from nodeconductor.core.filters import DjangoMappingFilterBackend

from nodeconductor.structure.filters import GenericRoleFilter
from nodeconductor.billing.backend import BillingBackendError
from nodeconductor.billing.models import PriceList, Invoice
from nodeconductor.billing.serializers import InvoiceSerializer


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
