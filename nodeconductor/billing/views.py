import django_filters

from rest_framework import viewsets, permissions, response, decorators, filters, exceptions

from django.conf import settings
from django.views.static import serve
from nodeconductor.core.filters import DjangoMappingFilterBackend

from nodeconductor.structure.filters import GenericRoleFilter
from nodeconductor.billing.serializers import InvoiceSerializer, InvoiceDetailedSerializer
from nodeconductor.billing.models import PriceList, Invoice


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
        ]
        order_by = [
            'date',
            '-date',
            'amount',
            '-amount',
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
    filter_backends = (GenericRoleFilter, filters.DjangoFilterBackend, DjangoMappingFilterBackend)
    lookup_field = 'uuid'
    permission_classes = (
        permissions.IsAuthenticated,
        permissions.DjangoObjectPermissions,
    )

    # Invoice items are being fetched directly from backend
    # thus we expose them in detailed view only
    # TODO: Move invoice items to DB and use single serializer
    def get_serializer_class(self):
        return InvoiceDetailedSerializer if self.action == 'retrieve' else InvoiceSerializer

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
