from rest_framework import serializers

from nodeconductor.core import models as core_models
from nodeconductor.core.serializers import PermissionFieldFilteringMixin
from nodeconductor.iaas import models


class InstanceCreateSerializer(PermissionFieldFilteringMixin,
                               serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Instance
        fields = ('url', 'hostname', 'description',
                  'template', 'flavor', 'project')
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
        fields = ('url', 'hostname', 'description',
                  'template', 'cloud', 'project', 'flavor', 'state')
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


class PurchaseSerializer(serializers.HyperlinkedModelSerializer):
    # TODO: Serialize customer and user with both url and name
    customer = serializers.Field(source='project.customer')
    user = serializers.Field(source='user.username')

    class Meta(object):
        model = models.Purchase
        fields = ('url', 'date', 'user', 'customer', 'project')
        lookup_field = 'uuid'


class ImageSerializer(PermissionFieldFilteringMixin,
                      serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Image
        fields = ('url', 'name', 'cloud', 'description',
                  'architecture', 'license_type')
        lookup_field = 'uuid'

    def get_filtered_field_names(self):
        return 'cloud',