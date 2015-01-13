from __future__ import unicode_literals

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework import serializers, status, exceptions

from nodeconductor.backup import serializers as backup_serializers
from nodeconductor.core import models as core_models, serializers as core_serializers
from nodeconductor.iaas import models
from nodeconductor.monitoring.zabbix.db_client import ZabbixDBClient
from nodeconductor.structure import serializers as structure_serializers, models as structure_models
from nodeconductor.structure import filters as structure_filters
from nodeconductor.structure.serializers import fix_non_nullable_attrs


class BasicCloudSerializer(core_serializers.BasicInfoSerializer):
    class Meta(core_serializers.BasicInfoSerializer.Meta):
        model = models.Cloud


class BasicFlavorSerializer(core_serializers.BasicInfoSerializer):
    class Meta(core_serializers.BasicInfoSerializer.Meta):
        model = models.Flavor


class FlavorSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Flavor
        fields = ('url', 'uuid', 'name', 'ram', 'disk', 'cores')
        lookup_field = 'uuid'


class CloudSerializer(core_serializers.PermissionFieldFilteringMixin,
                      core_serializers.RelatedResourcesFieldMixin,
                      serializers.HyperlinkedModelSerializer):
    flavors = FlavorSerializer(many=True, read_only=True)
    projects = structure_serializers.BasicProjectSerializer(many=True, read_only=True)
    customer_native_name = serializers.Field(source='customer.native_name')

    class Meta(object):
        model = models.Cloud
        fields = (
            'uuid',
            'url',
            'name',
            'customer', 'customer_name', 'customer_native_name',
            'flavors', 'projects', 'auth_url',
        )
        lookup_field = 'uuid'

    def get_fields(self):
        # TODO: Extract to a proper mixin
        fields = super(CloudSerializer, self).get_fields()

        try:
            method = self.context['view'].request.method
        except (KeyError, AttributeError):
            return fields

        if method in ('PUT', 'PATCH'):
            fields['auth_url'].read_only = True
            fields['customer'].read_only = True

        return fields

    def get_filtered_field_names(self):
        return 'customer',

    def get_related_paths(self):
        return 'customer',


class UniqueConstraintError(exceptions.APIException):
    status_code = status.HTTP_302_FOUND
    default_detail = 'Entity already exists.'


class CloudProjectMembershipSerializer(core_serializers.PermissionFieldFilteringMixin,
                                       core_serializers.RelatedResourcesFieldMixin,
                                       serializers.HyperlinkedModelSerializer):

    class Meta(object):
        model = models.CloudProjectMembership
        fields = (
            'url',
            'project', 'project_name',
            'cloud', 'cloud_name',
        )
        view_name = 'cloudproject_membership-detail'

    def get_filtered_field_names(self):
        return 'project', 'cloud'

    def get_related_paths(self):
        return 'project', 'cloud'

    def save(self, **kwargs):
        try:
            return super(CloudProjectMembershipSerializer, self).save(**kwargs)
        except IntegrityError:
            # unique constraint validation
            # TODO: Should be done on a higher level
            raise UniqueConstraintError()


class BasicSecurityGroupRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SecurityGroupRule
        fields = ('protocol', 'from_port', 'to_port', 'cidr')


class SecurityGroupSerializer(serializers.HyperlinkedModelSerializer):

    rules = BasicSecurityGroupRuleSerializer(read_only=True)
    cloud_project_membership = CloudProjectMembershipSerializer()

    class Meta(object):
        model = models.SecurityGroup
        fields = ('url', 'uuid', 'name', 'description', 'rules', 'cloud_project_membership')
        lookup_field = 'uuid'
        view_name = 'security_group-detail'

    # TODO: cleanup after migration to drf 3
    def validate(self, attrs):
        return fix_non_nullable_attrs(attrs)


class IpMappingSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = models.IpMapping
        fields = ('url', 'uuid', 'public_ip', 'private_ip', 'project')
        lookup_field = 'uuid'
        view_name = 'ip_mapping-detail'


class InstanceSecurityGroupSerializer(serializers.ModelSerializer):

    name = serializers.Field(source='security_group.name')
    rules = BasicSecurityGroupRuleSerializer(
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


class InstanceCreateSerializer(core_serializers.PermissionFieldFilteringMixin,
                               serializers.HyperlinkedModelSerializer):

    security_groups = InstanceSecurityGroupSerializer(
        many=True, required=False, allow_add_remove=True, read_only=False)
    project = serializers.HyperlinkedRelatedField(
        view_name='project-detail',
        lookup_field='uuid',
        queryset=structure_models.Project.objects.all(),
        required=True,
        write_only=True,
    )
    flavor = serializers.HyperlinkedRelatedField(
        view_name='flavor-detail',
        lookup_field='uuid',
        queryset=models.Flavor.objects.all(),
        required=True,
        write_only=True,
    )
    ssh_public_key = serializers.HyperlinkedRelatedField(
        view_name='sshpublickey-detail',
        lookup_field='uuid',
        queryset=core_models.SshPublicKey.objects.all(),
        required=False,
        write_only=True,
    )

    external_ips = core_serializers.IPsField(required=False)

    class Meta(object):
        model = models.Instance
        fields = (
            'url', 'uuid',
            'hostname', 'description',
            'template',
            'project',
            'security_groups', 'flavor', 'ssh_public_key', 'external_ips',
            'system_volume_size', 'data_volume_size',
        )
        lookup_field = 'uuid'

    def get_fields(self):
        fields = super(InstanceCreateSerializer, self).get_fields()

        try:
            request = self.context['view'].request
            user = request.user
        except (KeyError, AttributeError):
            return fields

        fields['ssh_public_key'].queryset = fields['ssh_public_key'].queryset.filter(user=user)
        fields['system_volume_size'].required = False

        clouds = structure_filters.filter_queryset_for_user(models.Cloud.objects.all(), user)
        fields['template'].queryset = fields['template'].queryset.filter(images__cloud__in=clouds).distinct()

        return fields

    def get_filtered_field_names(self):
        return 'project', 'flavor'

    def validate_security_groups(self, attrs, attr_name):
        if attr_name in attrs and attrs[attr_name] is None:
            del attrs[attr_name]
        return attrs

    def validate(self, attrs):
        flavor = attrs['flavor']
        project = attrs['project']
        try:
            membership = models.CloudProjectMembership.objects.get(
                project=project,
                cloud=flavor.cloud,
            )
        except models.CloudProjectMembership.DoesNotExist:
            raise ValidationError("Flavor is not within project's clouds.")

        external_ips = attrs.get('external_ips')
        if external_ips is not None:
            ip_exists = models.FloatingIP.objects.filter(
                address=external_ips,
                status='DOWN',
                cloud_project_membership=membership,
            ).exists()
            if not ip_exists:
                raise ValidationError("External IP is not from the list of available floating IPs.")

        template = attrs['template']
        images = list(models.Image.objects.filter(template=template, cloud=flavor.cloud))

        if not images:
            raise serializers.ValidationError("Template %s is not available on cloud %s"
                                              % (template, flavor.cloud))

        system_volume_size = attrs['system_volume_size'] if 'system_volume_size' in attrs else flavor.disk
        print system_volume_size, [im.min_disk for im in images]
        for image in images:
            if image.min_disk > system_volume_size:
                raise serializers.ValidationError("System volume size has to be greater then %s" % system_volume_size)

        # TODO: cleanup after migration to drf 3
        return fix_non_nullable_attrs(attrs)

    def restore_object(self, attrs, instance=None):
        key = attrs.get('ssh_public_key')
        if key:
            attrs['key_name'] = key.name
            attrs['key_fingerprint'] = key.fingerprint

        flavor = attrs['flavor']
        attrs['cores'] = flavor.cores
        attrs['ram'] = flavor.ram
        attrs['cloud'] = flavor.cloud
        if not 'system_volume_size' in attrs:
            attrs['system_volume_size'] = flavor.disk

        membership = models.CloudProjectMembership.objects.get(
            project=attrs['project'],
            cloud=flavor.cloud,
        )
        attrs['cloud_project_membership'] = membership

        return super(InstanceCreateSerializer, self).restore_object(attrs, instance)


class InstanceUpdateSerializer(serializers.HyperlinkedModelSerializer):

    security_groups = InstanceSecurityGroupSerializer(
        many=True, required=False, allow_add_remove=True, read_only=False)

    class Meta(object):
        model = models.Instance
        fields = ('url', 'hostname', 'description', 'security_groups')
        lookup_field = 'uuid'

    def validate_security_groups(self, attrs, attr_name):
        if attr_name in attrs and attrs[attr_name] is None:
            del attrs[attr_name]
        return attrs

    # TODO: cleanup after migration to drf 3
    def validate(self, attrs):
        return fix_non_nullable_attrs(attrs)


class InstanceSecurityGroupsInlineUpdateSerializer(serializers.Serializer):
    security_groups = InstanceSecurityGroupSerializer(
        many=True, required=False, read_only=False)


class InstanceResizeSerializer(core_serializers.PermissionFieldFilteringMixin,
                               serializers.Serializer):
    flavor = serializers.HyperlinkedRelatedField(
        view_name='flavor-detail',
        lookup_field='uuid',
        queryset=models.Flavor.objects.all(),
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


class InstanceSerializer(core_serializers.RelatedResourcesFieldMixin,
                         serializers.HyperlinkedModelSerializer):
    state = serializers.ChoiceField(choices=models.Instance.States.CHOICES, source='get_state_display')
    project_groups = structure_serializers.BasicProjectGroupSerializer(
        source='cloud_project_membership.project.project_groups', many=True, read_only=True)
    external_ips = core_serializers.IPsField()
    internal_ips = core_serializers.IPsField(read_only=True)
    backups = backup_serializers.BackupSerializer()
    backup_schedules = backup_serializers.BackupScheduleSerializer()

    security_groups = InstanceSecurityGroupSerializer(read_only=True)
    instance_licenses = InstanceLicenseSerializer(read_only=True)
    # special field for customer
    customer_abbreviation = serializers.Field(source='cloud_project_membership.project.customer.abbreviation')
    customer_native_name = serializers.Field(source='cloud_project_membership.project.customer.native_name')
    template_os = serializers.Field(source='template.os')

    class Meta(object):
        model = models.Instance
        fields = (
            'url', 'uuid', 'hostname', 'description', 'start_time',
            'template', 'template_name', 'template_os',
            'cloud', 'cloud_name', 'cloud_uuid',
            'project', 'project_name', 'project_uuid',
            'customer', 'customer_name', 'customer_native_name', 'customer_abbreviation',
            'key_name', 'key_fingerprint',
            'project_groups',
            'security_groups',
            'external_ips', 'internal_ips',
            'state',
            'backups', 'backup_schedules',
            'instance_licenses',
            'agreed_sla',
            'system_volume_size',
            'data_volume_size',
            'cores', 'ram',
        )
        read_only_fields = (
            'key_name',
            'system_volume_size',
            'data_volume_size',
        )
        lookup_field = 'uuid'

    def get_related_paths(self):
        return (
            'template',
            'cloud_project_membership.project',
            'cloud_project_membership.project.customer',
            'cloud_project_membership.cloud',
        )


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

    # TODO: cleanup after migration to drf 3
    def validate(self, attrs):
        return fix_non_nullable_attrs(attrs)


class FloatingIPSerializer(serializers.HyperlinkedModelSerializer):
    cloud_project_membership = CloudProjectMembershipSerializer()

    class Meta:
        model = models.FloatingIP
        fields = ('url', 'uuid', 'status', 'address', 'cloud_project_membership')
        lookup_field = 'uuid'
        view_name = 'floating_ip-detail'


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


class ServiceSerializer(serializers.Serializer):
    url = serializers.SerializerMethodField('get_service_url')
    service_type = serializers.SerializerMethodField('get_service_type')
    hostname = serializers.Field()
    uuid = serializers.Field()
    agreed_sla = serializers.Field()
    actual_sla = serializers.Field(source='slas__value')
    template_name = serializers.Field(source='template__name')
    customer_name = serializers.Field(source='cloud_project_membership__project__customer__name')
    customer_native_name = serializers.Field(source='cloud_project_membership__project__customer__native_name')
    customer_abbreviation = serializers.Field(source='cloud_project_membership__project__customer__abbreviation')
    project_name = serializers.Field(source='cloud_project_membership__project__name')
    project_groups = serializers.SerializerMethodField('get_project_groups')

    class Meta(object):
        fields = (
            'url',
            'uuid',
            'hostname', 'template_name',
            'customer_name',
            'customer_native_name',
            'customer_abbreviation',
            'project_name', 'project_groups',
            'agreed_sla', 'actual_sla',
            'service_type',
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
        service_instance = models.Instance.objects.get(uuid=obj['uuid'])
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

        service_instance = models.Instance.objects.get(uuid=obj['uuid'])
        groups = structure_serializers.BasicProjectGroupSerializer(
            service_instance.cloud_project_membership.project.project_groups.all(),
            many=True,
            read_only=True,
            context={'request': request}
        )
        return groups.data


class UsageStatsSerializer(serializers.Serializer):
    segments_count = serializers.IntegerField(min_value=0)
    start_timestamp = serializers.IntegerField(min_value=0)
    end_timestamp = serializers.IntegerField(min_value=0)
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


class SlaHistoryEventSerializer(serializers.Serializer):
    timestamp = serializers.IntegerField()
    state = serializers.CharField()


class StatsAggregateSerializer(serializers.Serializer):
    MODEL_NAME_CHOICES = (('project', 'project'), ('customer', 'customer'), ('project_group', 'project_group'))
    MODEL_CLASSES = {
        'project': structure_models.Project,
        'customer': structure_models.Customer,
        'project_group': structure_models.ProjectGroup,
    }

    model_name = serializers.ChoiceField(choices=MODEL_NAME_CHOICES)
    uuid = serializers.CharField(required=False)

    def get_projects(self, user):
        model = self.MODEL_CLASSES[self.data['model_name']]
        queryset = structure_filters.filter_queryset_for_user(model.objects.all(), user)

        if 'uuid' in self.data and self.data['uuid']:
            queryset = queryset.filter(uuid=self.data['uuid'])

        if self.data['model_name'] == 'project':
            return queryset.all()
        elif self.data['model_name'] == 'project_group':
            projects = structure_models.Project.objects.filter(project_groups__in=list(queryset))
            return structure_filters.filter_queryset_for_user(projects, user)
        else:
            projects = structure_models.Project.objects.filter(customer__in=list(queryset))
            return structure_filters.filter_queryset_for_user(projects, user)

    def get_memberships(self, user):
        projects = self.get_projects(user)
        return models.CloudProjectMembership.objects.filter(project__in=projects).all()
