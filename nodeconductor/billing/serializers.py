from rest_framework import serializers


class InvoiceSerializer(serializers.Serializer):
    url = serializers.HyperlinkedIdentityField(view_name='invoice-detail')
    uuid = serializers.ReadOnlyField()
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    amount = serializers.FloatField()
    customer_uuid = serializers.ReadOnlyField()
    customer_name = serializers.ReadOnlyField()
    customer_native_name = serializers.ReadOnlyField()
