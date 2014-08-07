from rest_framework import serializers

from nodeconductor.iaas import models
from nodeconductor.core import models as core_models
from nodeconductor.core.serializers import PermissionFieldFilteringMixin


class InstanceCreateSerializer(PermissionFieldFilteringMixin,
                               serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Instance
        fields = ('url', 'hostname', 'template', 'flavor', 'project')
        lookup_field = 'uuid'
        # TODO: Accept ip address count and volumes

    def get_filtered_field_names(self):
        return 'project', 'flavor'


class InstanceSerializer(PermissionFieldFilteringMixin,
                         serializers.HyperlinkedModelSerializer):
    cloud = serializers.HyperlinkedRelatedField(
        source='flavor.cloud',
        view_name='cloud-detail',
        lookup_field='uuid',
        read_only=True,
    )

    class Meta(object):
        model = models.Instance
        fields = ('url', 'hostname', 'template', 'cloud', 'project', 'flavor', 'state')
        lookup_field = 'uuid'
        # TODO: Render ip addresses and volumes

    def get_filtered_field_names(self):
        return 'project', 'flavor'


class TemplateSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Template
        fields = ('url', 'name')
        lookup_field = 'uuid'


class SshKeySerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = core_models.SshPublicKey
        fields = ('url', 'name', 'public_key')
        lookup_field = 'uuid'


class PurchaseSerializer(PermissionFieldFilteringMixin,
                         serializers.HyperlinkedModelSerializer):
    organization = serializers.Field(source='project.organization')
    user = serializers.Field(source='user.username')

    class Meta(object):
        model = models.Purchase
        fields = ('url', 'date', 'user', 'organization', 'project')
        lookup_field = 'uuid'

    def get_filtered_field_names(self):
        return 'project',