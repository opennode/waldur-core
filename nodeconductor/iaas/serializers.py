from rest_framework import serializers

from nodeconductor.structure.models import Role

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
        fields = ('url', 'state', 'flavor', 'hostname',
                  'template', 'cloud', 'project')
        lookup_field = 'uuid'
        # TODO: Render ip addresses and volumes

    def to_native(self, obj):
        ret = super(InstanceSerializer, self).to_native(obj)
        request = self.context['view'].request
        additional_fields = ('environment', 'state', 'uptime',
                             'flavor', 'IPs', 'hostname')
        if request.user in obj.project.roles. \
                get(role_type=Role.MANAGER).permission_group.user_set.all():
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
