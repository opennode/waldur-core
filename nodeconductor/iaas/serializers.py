from django.http import Http404
from rest_framework import serializers

from nodeconductor.backup import serializers as backup_serializers
from nodeconductor.core import models as core_models
from nodeconductor.core.serializers import PermissionFieldFilteringMixin, RelatedResourcesFieldMixin, IPsField
from nodeconductor.iaas import models
from nodeconductor.structure import serializers as structure_serializers


class InstanceSecurityGroupSerializer(serializers.ModelSerializer):

    security_group = serializers.HyperlinkedRelatedField(
        source='security_group',
        view_name='security_group-detail',
        lookup_field='uuid',
    )
    name = serializers.Field(source='security_group.name')
    protocol = serializers.Field(source='security_group.protocol')
    from_port = serializers.Field(source='security_group.from_port')
    to_port = serializers.Field(source='security_group.to_port')
    ip_range = serializers.Field(source='security_group.ip_range')
    netmask = serializers.Field(source='security_group.netmask')

    class Meta(object):
        model = models.InstanceSecurityGroup
        fields = ('security_group', 'name', 'protocol', 'from_port', 'to_port',
                  'ip_range', 'netmask',)
        lookup_field = 'uuid'


class InstanceCreateSerializer(PermissionFieldFilteringMixin,
                               serializers.HyperlinkedModelSerializer):

    security_groups = InstanceSecurityGroupSerializer(
        many=True, required=False, allow_add_remove=True, read_only=False)

    class Meta(object):
        model = models.Instance
        fields = ('url', 'hostname', 'description',
                  'template', 'flavor', 'project', 'security_groups', 'ssh_public_key')
        lookup_field = 'uuid'

    def __init__(self, *args, **kwargs):
        super(InstanceCreateSerializer, self).__init__(*args, **kwargs)
        self.user = kwargs['context']['user']

    def get_fields(self):
        fields = super(InstanceCreateSerializer, self).get_fields()

        try:
            request = self.context['view'].request
            user = request.user
        except (KeyError, AttributeError):
            return fields

        # TODO: Extract into a generic filter
        fields['ssh_public_key'].queryset = fields['ssh_public_key'].queryset.filter(user=user)

        return fields

    def get_filtered_field_names(self):
        return 'project', 'flavor'

    def validate_security_groups(self, attrs, attr_name):
        if attr_name in attrs and attrs[attr_name] is None:
            del attrs[attr_name]
        return attrs


class InstanceLicenseSerializer(serializers.ModelSerializer):

    name = serializers.Field(source='template_license.name')
    license_type = serializers.Field(source='template_license.license_type')
    service_type = serializers.Field(source='template_license.service_type')

    class Meta(object):
        model = models.InstanceLicense
        fields = (
            'uuid', 'name', 'license_type', 'service_type', 'setup_fee', 'monthly_fee',
        )
        lookup_field = 'uuid'


class InstanceSerializer(RelatedResourcesFieldMixin,
                         PermissionFieldFilteringMixin,
                         serializers.HyperlinkedModelSerializer):
    state = serializers.ChoiceField(choices=models.Instance.States.CHOICES, source='get_state_display')
    project_groups = structure_serializers.BasicProjectGroupSerializer(
        source='project.project_groups', many=True, read_only=True)
    external_ips = IPsField(source='external_ips', read_only=True)
    internal_ips = IPsField(source='internal_ips', read_only=True)
    ssh_public_key_name = serializers.Field(source='ssh_public_key.name')
    backups = backup_serializers.BackupSerializer()
    backup_schedules = backup_serializers.BackupScheduleSerializer()

    security_groups = InstanceSecurityGroupSerializer(read_only=True)
    instance_licenses = InstanceLicenseSerializer(read_only=True)
    # special field for customer
    customer_abbreviation = serializers.Field(source='project.customer.abbreviation')

    class Meta(object):
        model = models.Instance
        fields = (
            'url', 'uuid', 'hostname', 'description', 'start_time',
            'template', 'template_name',
            'cloud', 'cloud_name',
            'flavor', 'flavor_name',
            'project', 'project_name',
            'customer', 'customer_name', 'customer_abbreviation',
            'ssh_public_key', 'ssh_public_key_name',
            'project_groups',
            'security_groups',
            'external_ips', 'internal_ips',
            'state',
            'backups', 'backup_schedules',
            'instance_licenses'
        )
        read_only_fields = ('ssh_public_key',)
        lookup_field = 'uuid'

    def get_filtered_field_names(self):
        return 'project', 'flavor'

    def get_related_paths(self):
        return 'flavor.cloud', 'template', 'project', 'flavor', 'project.customer'


class TemplateLicenseSerializer(serializers.HyperlinkedModelSerializer):

    projects_groups = structure_serializers.BasicProjectGroupSerializer(
        source='get_projects_groups', many=True, read_only=True)

    projects = structure_serializers.BasicProjectSerializer(
        source='get_projects', many=True, read_only=True)

    class Meta(object):
        model = models.TemplateLicense
        fields = (
            'url', 'uuid', 'name', 'license_type', 'service_type', 'setup_fee', 'monthly_fee',
            'projects', 'projects_groups',
        )
        lookup_field = 'uuid'


class TemplateSerializer(serializers.HyperlinkedModelSerializer):

    template_licenses = TemplateLicenseSerializer()

    class Meta(object):
        model = models.Template
        fields = (
            'url', 'uuid',
            'name', 'description', 'icon_url',
            'os',
            'is_active',
            'setup_fee',
            'monthly_fee',
            'template_licenses',
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


class TemplateCreateSerializer(serializers.HyperlinkedModelSerializer):

    class Meta(object):
        model = models.Template
        fields = (
            'url', 'uuid',
            'name', 'description', 'icon_url',
            'os',
            'is_active',
            'setup_fee',
            'monthly_fee',
            'template_licenses',
        )
        lookup_field = 'uuid'


class SshKeySerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = core_models.SshPublicKey
        fields = ('url', 'uuid', 'name', 'public_key', 'fingerprint')
        read_only_fields = ('fingerprint',)
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


# XXX: this serializer have to be removed after haystack implementation
class ServiceSerializer(RelatedResourcesFieldMixin, serializers.HyperlinkedModelSerializer):

    agreed_sla = serializers.SerializerMethodField('get_agreed_sla')
    actual_sla = serializers.SerializerMethodField('get_actual_sla')
    service_type = serializers.SerializerMethodField('get_service_type')
    project_groups = structure_serializers.BasicProjectGroupSerializer(
        source='project.project_groups', many=True, read_only=True)
    name = serializers.Field(source="hostname")

    class Meta(object):
        model = models.Instance
        fields = (
            'url', 'project_name', 'name', 'project_groups', 'agreed_sla', 'actual_sla',
        )
        view_name = 'service-detail'
        lookup_field = 'uuid'

    def get_related_paths(self):
        return 'project',

    def get_agreed_sla(self, obj):
        return 100

    def get_actual_sla(self, obj):
        return 97

    def get_service_type(self, obj):
        return 'IaaS'
