from rest_framework import serializers

from nodeconductor.core import serializers as core_serializers
from nodeconductor.billing.models import Invoice


class InvoiceSerializer(core_serializers.AugmentedSerializerMixin,
                        serializers.HyperlinkedModelSerializer):

    year = serializers.DateField(format='%Y', source='date')
    month = serializers.DateField(format='%m', source='date')
    customer_native_name = serializers.ReadOnlyField(source='customer.native_name')
    pdf = serializers.HyperlinkedIdentityField(view_name='invoice-pdf', lookup_field='uuid')

    class Meta(object):
        model = Invoice
        fields = (
            'url', 'uuid', 'year', 'month', 'amount', 'pdf', 'date',
            'customer', 'customer_uuid', 'customer_name', 'customer_native_name',
            'status',
        )
        related_paths = ('customer',)
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'customer': {'lookup_field': 'uuid'},
        }
