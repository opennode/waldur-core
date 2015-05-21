import django_filters

from rest_framework import viewsets, permissions, response, decorators, filters

from decimal import Decimal
from django.http import HttpResponse
from reportlab.pdfgen import canvas

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

    def get_serializer_class(self):
        return InvoiceDetailedSerializer if self.action == 'retrieve' else InvoiceSerializer

    @decorators.detail_route()
    def pdf(self, request, uuid=None):
        invoice = self.get_object()

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="invoice.pdf"'

        pdf = canvas.Canvas(response)
        pdf.drawString(100, 800, str(invoice))
        pdf.showPage()
        pdf.save()
        return response
