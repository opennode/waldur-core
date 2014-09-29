from rest_framework import serializers

from nodeconductor.core import models as core_models
from nodeconductor.core.serializers import PermissionFieldFilteringMixin, RelatedResourcesFieldMixin
from nodeconductor.iaas import models
from nodeconductor.structure import serializers as structure_serializers


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


class InstanceSerializer(RelatedResourcesFieldMixin,
                         PermissionFieldFilteringMixin,
                         serializers.HyperlinkedModelSerializer):
    state = serializers.ChoiceField(choices=models.Instance.States.CHOICES, source='get_state_display')
    project_groups = structure_serializers.BasicProjectGroupSerializer(
        source='project.project_groups', many=True, read_only=True)

    class Meta(object):
        model = models.Instance
        fields = (
            'url', 'hostname', 'description', 'start_time',
            'template', 'template_name',
            'cloud', 'cloud_name',
            'flavor', 'flavor_name',
            'project', 'project_name',
            'customer', 'customer_name',
            'project_groups',
            'ips',
            # TODO: add security groups 1:N (source, port, proto, desc, url)
            'state',
        )

        read_only_fields = ('ips',)
        lookup_field = 'uuid'

    def get_filtered_field_names(self):
        return 'project', 'flavor'

    def get_related_paths(self):
        return 'flavor.cloud', 'template', 'project', 'flavor', 'project.customer'


class TemplateSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Template
        fields = (
            'url',
            'name', 'description', 'icon_url',
            'os',
            'is_active',
            'setup_fee',
            'monthly_fee',
        )
        lookup_field = 'uuid'

    def get_fields(self):
        fields = super(TemplateSerializer, self).get_fields()

        try:
            user = self.context['request'].user
        except (KeyError, AttributeError):
            return fields

        if not user.is_staff:
            del fields['is_active']

        return fields


class SshKeySerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = core_models.SshPublicKey
        fields = ('url', 'name', 'public_key')
        lookup_field = 'uuid'


class PurchaseSerializer(RelatedResourcesFieldMixin, serializers.HyperlinkedModelSerializer):
    user = serializers.HyperlinkedRelatedField(
        source='user',
        view_name='user-detail',
        lookup_field='uuid',
        read_only=True,
    )
    user_full_name = serializers.Field(source='user.full_name')
    user_native_name = serializers.Field(source='user.native_name')

    class Meta(object):
        model = models.Purchase
        fields = (
            'url', 'date',
            'user', 'user_full_name', 'user_native_name',
            'customer', 'customer_name',
            'project', 'project_name',
        )
        lookup_field = 'uuid'

    def get_related_paths(self):
        return 'project.customer', 'project'


class ImageSerializer(RelatedResourcesFieldMixin,
                      PermissionFieldFilteringMixin,
                      serializers.HyperlinkedModelSerializer):
    architecture = serializers.ChoiceField(choices=models.Image.ARCHITECTURE_CHOICES, source='get_architecture_display')

    class Meta(object):
        model = models.Image
        fields = (
            'url', 'name', 'description',
            'cloud', 'cloud_name',
            'architecture',
        )
        lookup_field = 'uuid'

    def get_filtered_field_names(self):
        return 'cloud',

    def get_related_paths(self):
        return 'cloud',
