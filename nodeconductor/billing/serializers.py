from rest_framework import serializers

from nodeconductor.core import serializers as core_serializers
from nodeconductor.billing.models import Invoice


class InvoiceSerializer(core_serializers.AugmentedSerializerMixin,
                        serializers.HyperlinkedModelSerializer):

    year = serializers.DateField(format='%Y', source='date')
    month = serializers.DateField(format='%m', source='date')
    customer_native_name = serializers.ReadOnlyField(source='customer.native_name')

    class Meta(object):
        model = Invoice
        fields = (
            'url', 'uuid', 'year', 'month', 'amount',
            'customer', 'customer_uuid', 'customer_name', 'customer_native_name'
        )
        related_paths = ('customer',)
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'customer': {'lookup_field': 'uuid'},
        }


class InvoiceDetailedSerializer(InvoiceSerializer):

    def get_items(self, obj):
        # TODO: Move it to createsampleinvoices
        if not obj.backend_id:
            # Dummy items
            return [
                {
                    "amount": "7.95",
                    "type": "Hosting",
                    "name": "Home Package - topcorp.tv (02/10/2014 - 01/11/2014)"
                }
            ]

        backend = obj.customer.get_billing_backend()
        return backend.get_invoice_items(obj.backend_id)

    def get_fields(self):
        fields = super(InvoiceDetailedSerializer, self).get_fields()
        fields['items'] = serializers.SerializerMethodField()
        return fields
