from rest_framework import serializers

from nodeconductor.billing.models import Invoice, Payment
from nodeconductor.core import serializers as core_serializers


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
        )
        related_paths = ('customer',)
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'customer': {'lookup_field': 'uuid'},
        }


class PaymentSerializer(core_serializers.AugmentedSerializerMixin,
                        serializers.HyperlinkedModelSerializer):

    amount = serializers.DecimalField(max_digits=9, decimal_places=2)
    state = serializers.ReadOnlyField(source='get_state_display')

    class Meta(object):
        model = Payment

        fields = (
            'url', 'uuid', 'created', 'modified', 'state',
            'amount', 'customer', 'approval_url'
        )

        read_only_fields = ('approval_url',)
        protected_fields = ('customer', 'amount')

        extra_kwargs = {
            'url': {'lookup_field': 'uuid', 'view_name': 'payment-detail'},
            'customer': {'lookup_field': 'uuid', 'view_name': 'customer-detail'},
        }


class PaymentApproveSerializer(serializers.Serializer):
    payment_id = serializers.CharField()
    payer_id = serializers.CharField()

    def validate(self, validated_data):
        if self.instance.backend_id != validated_data['payment_id']:
            raise serializers.ValidationError('Invalid paymentId')
        return validated_data
