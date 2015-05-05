from rest_framework import serializers


class InvoiceSerializer(serializers.Serializer):
    url = serializers.HyperlinkedIdentityField(view_name='invoice-detail')
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    customer_uuid = serializers.ReadOnlyField()
    customer_name = serializers.ReadOnlyField()
    customer_native_name = serializers.ReadOnlyField()
