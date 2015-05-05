from rest_framework import viewsets, mixins, exceptions, response, decorators

from django.http import HttpResponse
from reportlab.pdfgen import canvas

from nodeconductor.billing.dummy import DummyDataSet
from nodeconductor.billing.serializers import InvoiceSerializer
from nodeconductor.billing.filters import InvoiceSearchFilter


class BillingViewSet(viewsets.GenericViewSet):

    @decorators.list_route()
    def pricelist(self, request):
        return response.Response(DummyDataSet.PRICELIST)


class InvoiceViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = InvoiceSerializer
    filter_backends = (InvoiceSearchFilter,)

    def get_queryset(self):
        return DummyDataSet.invoices_queryset()

    def get_object(self):
        try:
            return next(obj for obj in self.get_queryset() if obj.pk == self.kwargs['pk'])
        except StopIteration as e:
            raise exceptions.NotFound(e)

    @decorators.detail_route()
    def pdf(self, request, pk=None):
        invoice = self.get_object()

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="invoice.pdf"'

        pdf = canvas.Canvas(response)
        pdf.drawString(100, 800, "{month}/{year} {customer_native_name} {amount}".format(**invoice.__dict__))
        pdf.showPage()
        pdf.save()
        return response
