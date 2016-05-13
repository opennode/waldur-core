from nodeconductor.structure import serializers as structure_serializers
from .models import TestService


class ServiceSerializer(structure_serializers.BaseServiceSerializer):
    class Meta(structure_serializers.BaseServiceSerializer.Meta):
        model = TestService
