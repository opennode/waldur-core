import django_filters

from rest_framework import viewsets, permissions, response, decorators, filters, exceptions

from decimal import Decimal
from django.conf import settings
from django.views.static import serve

from nodeconductor.structure.filters import GenericRoleFilter
from nodeconductor.billing.serializers import InvoiceSerializer, InvoiceDetailedSerializer
from nodeconductor.billing.models import Invoice


class BillingViewSet(viewsets.GenericViewSet):

    @decorators.list_route()
    def pricelist(self, request):
        dummy_pricelist = dict(
            core=Decimal('1000'),
            ram_mb=Decimal('500'),
            storage_mb=Decimal('300'),
            license_type=Decimal('700'),
        )

        return response.Response(dummy_pricelist)


class InvoiceFilter(django_filters.FilterSet):
    customer = django_filters.CharFilter(name='customer__uuid', distinct=True)
    month = django_filters.CharFilter(name='date', lookup_type='month')
    year = django_filters.CharFilter(name='date', lookup_type='year')

    class Meta(object):
        model = Invoice
        fields = ('customer', 'year', 'month')


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Invoice.objects.all()
    filter_class = InvoiceFilter
    filter_backends = (GenericRoleFilter, filters.DjangoFilterBackend)
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
