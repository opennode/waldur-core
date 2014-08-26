from rest_framework import serializers

from nodeconductor.iaas import models
from nodeconductor.core import models as core_models
from nodeconductor.core.serializers import PermissionFieldFilteringMixin
from nodeconductor.structure.models import ProjectRole


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
        fields = ('url', 'hostname', 'description', 'template', 
                  'uptime', 'ips', 'cloud', 'project', 'flavor', 'state')
        lookup_field = 'uuid'
        # TODO: Render ip addresses and volumes

    def to_native(self, instance):
        ret = super(InstanceSerializer, self).to_native(instance)
        request = self.context['view'].request
        additional_fields = ('state', 'uptime',
                             'flavor', 'ips', 'hostname')
        if request.user in instance.project.roles. \
                get(role_type=ProjectRole.MANAGER).permission_group.user_set.all():
            for k in ret.keys():
                if k in additional_fields:
                    del ret[k]
        return ret

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
    customer = serializers.Field(source='project.customer')
    user = serializers.Field(source='user.username')

    class Meta(object):
        model = models.Purchase
        fields = ('url', 'date', 'user', 'customer', 'project')
        lookup_field = 'uuid'

    def get_filtered_field_names(self):
        return 'project',
