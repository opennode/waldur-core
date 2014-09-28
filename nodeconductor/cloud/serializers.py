from rest_framework import serializers

from nodeconductor.core import serializers as core_serializers
from nodeconductor.cloud import models


class BasicCloudSerializer(core_serializers.BasicInfoSerializer):
    class Meta(core_serializers.BasicInfoSerializer.Meta):
        model = models.Cloud


class BasicFlavorSerializer(core_serializers.BasicInfoSerializer):
    class Meta(core_serializers.BasicInfoSerializer.Meta):
        model = models.Flavor


class FlavorSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Flavor
        fields = ('url', 'name', 'ram', 'disk', 'cores')
        lookup_field = 'uuid'


class CloudSerializer(core_serializers.PermissionFieldFilteringMixin,
                      core_serializers.RelatedResourcesFieldMixin,
                      serializers.HyperlinkedModelSerializer):
    flavors = FlavorSerializer(many=True, read_only=True)

    class Meta(object):
        model = models.Cloud
        fields = ('uuid', 'url', 'name', 'customer', 'customer_name', 'flavors')
        lookup_field = 'uuid'

    def get_filtered_field_names(self):
        return 'customer',

    def get_related_paths(self):
        return 'customer',


class CloudProjectMembershipSerializer(core_serializers.PermissionFieldFilteringMixin,
                                       core_serializers.RelatedResourcesFieldMixin,
                                       serializers.HyperlinkedModelSerializer):

    class Meta(object):
        model = models.Cloud.projects.through
        fields = (
            'url',
            'project', 'project_name',
            'cloud', 'cloud_name',
        )
        view_name = 'projectcloud_membership-detail'

    def get_filtered_field_names(self):
        return 'project', 'cloud'

    def get_related_paths(self):
        return 'project', 'cloud'
