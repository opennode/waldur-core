from rest_framework import serializers

from nodeconductor.core import serializers as core_serializers
from nodeconductor.cloud import models


class BasicCloudSerializer(core_serializers.BasicInfoSerializer):
    class Meta(core_serializers.BasicInfoSerializer.Meta):
        model = models.Cloud


class CloudSerializer(core_serializers.PermissionFieldFilteringMixin,
                      serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Cloud
        fields = ('uuid', 'url', 'name', 'customer')
        lookup_field = 'uuid'

    def get_filtered_field_names(self):
        return 'customer',


class FlavorSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Flavor
        fields = ('url', 'name', 'ram', 'disk', 'cores')
        lookup_field = 'uuid'
