from __future__ import unicode_literals

from rest_framework import serializers
from rest_framework.reverse import reverse

from nodeconductor.backup import serializers as backup_serializers
from nodeconductor.cloud import models as cloud_models
from nodeconductor.cloud import serializers as cloud_serializers
from nodeconductor.core import models as core_models
from nodeconductor.core.serializers import PermissionFieldFilteringMixin, RelatedResourcesFieldMixin, IPsField
from nodeconductor.iaas import models
from nodeconductor.iaas.models import Instance
from nodeconductor.monitoring.zabbix.db_client import ZabbixDBClient
from nodeconductor.structure import serializers as structure_serializers


class InstanceSecurityGroupSerializer(serializers.ModelSerializer):

    name = serializers.Field(source='security_group.name')
    rules = cloud_serializers.BasicSecurityGroupRuleSerializer(
        source='security_group.rules',
        many=True,
        read_only=True
    )
    url = serializers.HyperlinkedRelatedField(source='security_group', lookup_field='uuid',
                                              view_name='security_group-detail')
    description = serializers.Field(source='security_group.description')

    class Meta(object):
        model = models.InstanceSecurityGroup
        fields = ('url', 'name', 'rules', 'description')
        lookup_field = 'uuid'
        view_name = 'security_group-detail'


class InstanceCreateSerializer(PermissionFieldFilteringMixin,
                               serializers.HyperlinkedModelSerializer):

    security_groups = InstanceSecurityGroupSerializer(
        many=True, required=False, allow_add_remove=True, read_only=False)

    class Meta(object):
        model = models.Instance
        fields = ('url', 'hostname', 'description',
                  'template', 'flavor', 'project', 'security_groups', 'ssh_public_key')
        lookup_field = 'uuid'

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


class InstanceUpdateSerializer(serializers.HyperlinkedModelSerializer):

    security_groups = InstanceSecurityGroupSerializer(
        many=True, required=False, allow_add_remove=True, read_only=False)

    class Meta(object):
        model = models.Instance
        # fields = ('url', 'hostname', 'description')
        fields = ('url', 'hostname', 'description', 'security_groups')
        lookup_field = 'uuid'

    def validate_security_groups(self, attrs, attr_name):
        if attr_name in attrs and attrs[attr_name] is None:
            del attrs[attr_name]
        return attrs


class InstanceSecurityGroupsInlineUpdateSerializer(serializers.Serializer):
    security_groups = InstanceSecurityGroupSerializer(
        many=True, required=False, read_only=False)


class InstanceResizeSerializer(PermissionFieldFilteringMixin,
                               serializers.Serializer):
    flavor = serializers.HyperlinkedRelatedField(
        view_name='flavor-detail',
        lookup_field='uuid',
        queryset=cloud_models.Flavor.objects.all(),
        required=False,
    )
    disk_size = serializers.IntegerField(min_value=1, required=False)

    def get_filtered_field_names(self):
        return 'flavor',

    def validate(self, attrs):
        flavor = attrs.get('flavor')
        disk_size = attrs.get('disk_size')

        if flavor is not None and disk_size is not None:
            raise serializers.ValidationError("Cannot resize both disk size and flavor simultaneously")
        if flavor is None and disk_size is None:
            raise serializers.ValidationError("Either disk_size or flavor is required")

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
    template_os = serializers.Field(source='template.os')

    class Meta(object):
        model = models.Instance
        fields = (
            'url', 'uuid', 'hostname', 'description', 'start_time',
            'template', 'template_name', 'template_os',
            'cloud', 'cloud_name', 'cloud_uuid',
            'flavor', 'flavor_name',
            'project', 'project_name', 'project_uuid',
            'customer', 'customer_name', 'customer_abbreviation',
            'ssh_public_key', 'ssh_public_key_name',
            'project_groups',
            'security_groups',
            'external_ips', 'internal_ips',
            'state',
            'backups', 'backup_schedules',
            'instance_licenses',
            'system_volume_size',
            'data_volume_size',
            'agreed_sla'
        )
        read_only_fields = (
            'ssh_public_key',
            'system_volume_size',
            'data_volume_size',
        )
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
            'sla_level',
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
            'sla_level',
            'setup_fee',
            'monthly_fee',
            'template_licenses',
        )
        lookup_field = 'uuid'


class SshKeySerializer(serializers.HyperlinkedModelSerializer):
    user_uuid = serializers.Field(source='user.uuid')

    class Meta(object):
        model = core_models.SshPublicKey
        fields = ('url', 'uuid', 'name', 'public_key', 'fingerprint', 'user_uuid')
        read_only_fields = ('fingerprint',)
        lookup_field = 'uuid'

    def validate(self, attrs):
        """
        Check that the start is before the stop.
        """
        try:
            request = self.context['view'].request
            user = request.user
        except (KeyError, AttributeError):
            return attrs

        name = attrs['name']
        if core_models.SshPublicKey.objects.filter(user=user, name=name).exists():
            raise serializers.ValidationError('SSH key name is not unique for a user')
        return attrs

    def get_fields(self):
        fields = super(SshKeySerializer, self).get_fields()

        try:
            user = self.context['request'].user
        except (KeyError, AttributeError):
            return fields

        if not user.is_staff:
            del fields['user_uuid']

        return fields


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


class ServiceSerializer(serializers.Serializer):
    url = serializers.SerializerMethodField('get_service_url')
    service_type = serializers.SerializerMethodField('get_service_type')
    hostname = serializers.Field()
    agreed_sla = serializers.Field()
    actual_sla = serializers.Field(source='slas__value')
    template_name = serializers.Field(source='template__name')
    customer_name = serializers.Field(source='project__customer__name')
    project_name = serializers.Field(source='project__name')
    project_groups = serializers.SerializerMethodField('get_project_groups')

    class Meta(object):
        fields = (
            'url',
            'hostname', 'template_name',
            'customer_name',
            'project_name', 'project_groups',
            'agreed_sla', 'actual_sla',
            'service_type'
        )
        view_name = 'service-detail'
        lookup_field = 'uuid'

    def get_service_type(self, obj):
        return 'IaaS'

    def get_service_url(self, obj):
        try:
            request = self.context['request']
        except (KeyError, AttributeError):
            raise AttributeError('ServiceSerializer has to be initialized with `request` in context')

        # TODO: this could use something similar to backup's generic model for all resources
        view_name = 'service-detail'
        service_instance = Instance.objects.get(uuid=obj['uuid'])
        hyperlinked_field = serializers.HyperlinkedRelatedField(
            view_name=view_name,
            lookup_field='uuid',
            read_only=True,
        )
        return hyperlinked_field.get_url(service_instance, view_name, request, format=None)

    # TODO: this shouldn't come from this endpoint, but UI atm depends on it
    def get_project_groups(self, obj):
        try:
            request = self.context['request']
        except (KeyError, AttributeError):
            raise AttributeError('ServiceSerializer has to be initialized with `request` in context')

        service_instance = Instance.objects.get(uuid=obj['uuid'])
        groups = structure_serializers.BasicProjectGroupSerializer(
            service_instance.project.project_groups.all(),
            many=True,
            read_only=True,
            context={'request': request}
        )
        return groups.data


class UsageStatsSerializer(serializers.Serializer):
    segments_count = serializers.IntegerField()
    start_timestamp = serializers.IntegerField()
    end_timestamp = serializers.IntegerField()
    item = serializers.CharField()

    def validate_item(self, attrs, name):
        item = attrs[name]
        if not item in ZabbixDBClient.items:
            raise serializers.ValidationError(
                "GET parameter 'item' have to be from list: %s" % ZabbixDBClient.items.keys())
        return attrs

    def get_stats(self, instances):
        self.attrs = self.data
        zabbix_db_client = ZabbixDBClient()
        return zabbix_db_client.get_item_stats(
            instances, self.data['item'],
            self.data['start_timestamp'], self.data['end_timestamp'], self.data['segments_count'])
