from rest_framework import serializers


class VmSerializer(serializers.Serializer):
    image = serializers.CharField(max_length=200)  # TODO: Figure out proper max length
    volume_size = serializers.IntegerField(min_value=1, required=False)
