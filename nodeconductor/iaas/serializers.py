from rest_framework import serializers

from nodeconductor.core import models as core_models
from nodeconductor.backup import serializers as backup_serializers
from nodeconductor.core.serializers import PermissionFieldFilteringMixin, RelatedResourcesFieldMixin, IPsField
from nodeconductor.iaas import models
from nodeconductor.structure import serializers as structure_serializers


class InstanceSecurityGroupSerializer(serializers.ModelSerializer):

    protocol = serializers.CharField(read_only=True)
    from_port = serializers.CharField(read_only=True)
    to_port = serializers.CharField(read_only=True)
    ip_range = serializers.CharField(read_only=True)

    class Meta(object):
        model = models.InstanceSecurityGroup
        fields = ('name', 'protocol', 'from_port', 'to_port', 'ip_range')


class InstanceCreateSerializer(PermissionFieldFilteringMixin,
                               serializers.HyperlinkedModelSerializer):

    security_groups = InstanceSecurityGroupSerializer(
        many=True, required=False, allow_add_remove=True, read_only=False)

    class Meta(object):
        model = models.Instance
        fields = ('url', 'hostname', 'description',
                  'template', 'flavor', 'project', 'security_groups')
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
    ips = IPsField(source='ips', read_only=True)

    backups = backup_serializers.BackupSerializer()
    backup_schedules = backup_serializers.BackupScheduleSerializer()

    security_groups = InstanceSecurityGroupSerializer(
        many=True, required=False, allow_add_remove=True, read_only=False)

    class Meta(object):
        model = models.Instance
        fields = (
            'url', 'uuid', 'hostname', 'description', 'start_time',
            'template', 'template_name',
            'cloud', 'cloud_name',
            'flavor', 'flavor_name',
            'project', 'project_name',
            'customer', 'customer_name',
            'project_groups', 'security_groups',
            'ips',
            # TODO: add security groups 1:N (source, port, proto, desc, url)
            'state',
            'backups', 'backup_schedules'
        )

        lookup_field = 'uuid'

    def get_filtered_field_names(self):
        return 'project', 'flavor'

    def get_related_paths(self):
        return 'flavor.cloud', 'template', 'project', 'flavor', 'project.customer'


class TemplateSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Template
        fields = (
            'url', 'uuid',
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
        fields = ('url', 'uuid', 'name', 'public_key')
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
            'url', 'uuid', 'date',
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
            'url', 'uuid', 'name', 'description',
            'cloud', 'cloud_name',
            'architecture',
        )
        lookup_field = 'uuid'

    def get_filtered_field_names(self):
        return 'cloud',

    def get_related_paths(self):
        return 'cloud',
