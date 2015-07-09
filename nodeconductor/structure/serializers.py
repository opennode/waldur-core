from __future__ import unicode_literals

from django.core.validators import RegexValidator
from django.contrib import auth
from django.db import models as django_models
from django.conf import settings
from django.utils import six
from django.utils.encoding import force_text
from rest_framework import serializers, exceptions

from nodeconductor.core import serializers as core_serializers
from nodeconductor.core import models as core_models
from nodeconductor.core import utils as core_utils
from nodeconductor.core.tasks import send_task
from nodeconductor.core.fields import MappedChoiceField
from nodeconductor.quotas import serializers as quotas_serializers
from nodeconductor.structure import models, filters
from nodeconductor.structure.filters import filter_queryset_for_user


# The regestry of all supported services
# TODO: Move OpenstackSettings to ServiceSettings and remove this hardcoding
SUPPORTED_SERVICES = {
    'iaas.cloud': {
        'name': 'OpenStack',
        'view_name': 'cloud-list',
        'resources': {
            'iaas.instance': {'name': 'Instance', 'view_name': 'iaas-resource-list'}
        },
    },
}

User = auth.get_user_model()


class PermissionFieldFilteringMixin(object):
    """
    Mixin allowing to filter related fields.

    In order to constrain the list of entities that can be used
    as a value for the field:

    1. Make sure that the entity in question has corresponding
       Permission class defined.

    2. Implement `get_filtered_field_names()` method
       in the class that this mixin is mixed into and return
       the field in question from that method.
    """
    def get_fields(self):
        fields = super(PermissionFieldFilteringMixin, self).get_fields()

        try:
            request = self.context['request']
            user = request.user
        except (KeyError, AttributeError):
            return fields

        for field_name in self.get_filtered_field_names():
            fields[field_name].queryset = filter_queryset_for_user(
                fields[field_name].queryset, user)

        return fields

    def get_filtered_field_names(self):
        raise NotImplementedError(
            'Implement get_filtered_field_names() '
            'to return list of filtered fields')


class BasicUserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = User
        fields = ('url', 'uuid', 'username', 'full_name', 'native_name',)
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


class BasicProjectSerializer(core_serializers.BasicInfoSerializer):
    class Meta(core_serializers.BasicInfoSerializer.Meta):
        model = models.Project
        fields = ('url', 'uuid', 'name')


class BasicProjectGroupSerializer(core_serializers.BasicInfoSerializer):
    class Meta(core_serializers.BasicInfoSerializer.Meta):
        model = models.ProjectGroup
        fields = ('url', 'name', 'uuid')
        read_only_fields = ('name', 'uuid')


class NestedProjectGroupSerializer(core_serializers.HyperlinkedRelatedModelSerializer):
    class Meta(object):
        model = models.ProjectGroup
        fields = ('url', 'name', 'uuid')
        read_only_fields = ('name', 'uuid')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


class ProjectSerializer(PermissionFieldFilteringMixin,
                        core_serializers.AugmentedSerializerMixin,
                        serializers.HyperlinkedModelSerializer):
    project_groups = NestedProjectGroupSerializer(
        queryset=models.ProjectGroup.objects.all(),
        many=True,
        required=False,
        default=(),
    )

    quotas = quotas_serializers.QuotaSerializer(many=True, read_only=True)
    # These fields exist for backward compatibility
    resource_quota = serializers.SerializerMethodField('get_resource_quotas')
    resource_quota_usage = serializers.SerializerMethodField('get_resource_quotas_usage')

    class Meta(object):
        model = models.Project
        fields = (
            'url', 'uuid',
            'name',
            'customer', 'customer_uuid', 'customer_name', 'customer_native_name', 'customer_abbreviation',
            'project_groups',
            'description',
            'quotas',
            'resource_quota', 'resource_quota_usage',
            'created',
        )
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'customer': {'lookup_field': 'uuid'},
        }
        related_paths = {
            'customer': ('uuid', 'name', 'native_name', 'abbreviation')
        }

    def create(self, validated_data):
        project_groups = validated_data.pop('project_groups')
        project = super(ProjectSerializer, self).create(validated_data)
        project.project_groups.add(*project_groups)

        return project

    def get_resource_quotas(self, obj):
        return models.Project.get_sum_of_quotas_as_dict(
            [obj], ['ram', 'storage', 'max_instances', 'vcpu'], fields=['limit'])

    def get_resource_quotas_usage(self, obj):
        quota_values = models.Project.get_sum_of_quotas_as_dict(
            [obj], ['ram', 'storage', 'max_instances', 'vcpu'], fields=['usage'])
        # No need for '_usage' suffix in quotas names
        return {
            key[:-6]: value for key, value in quota_values.iteritems()
        }

    def get_filtered_field_names(self):
        return 'customer',

    def update(self, instance, validated_data):
        if 'project_groups' in validated_data:
            project_groups = validated_data.pop('project_groups')
            instance.project_groups.clear()
            instance.project_groups.add(*project_groups)
        return super(ProjectSerializer, self).update(instance, validated_data)


class DefaultImageField(serializers.ImageField):
    def to_representation(self, image):
        if image:
            return super(DefaultImageField, self).to_representation(image)
        else:
            return settings.NODECONDUCTOR.get('DEFAULT_CUSTOMER_LOGO')


class CustomerImageSerializer(serializers.ModelSerializer):
    image = serializers.ImageField()

    class Meta:
        model = models.Customer
        fields = ['image']


class CustomerSerializer(core_serializers.AugmentedSerializerMixin,
                         serializers.HyperlinkedModelSerializer):
    projects = serializers.SerializerMethodField()
    project_groups = serializers.SerializerMethodField()
    owners = BasicUserSerializer(source='get_owners', many=True, read_only=True)
    image = DefaultImageField(required=False, read_only=True)
    quotas = quotas_serializers.QuotaSerializer(many=True, read_only=True)

    class Meta(object):
        model = models.Customer
        fields = (
            'url',
            'uuid',
            'name', 'native_name', 'abbreviation', 'contact_details',
            'projects', 'project_groups',
            'owners', 'balance',
            'registration_code',
            'quotas',
            'image'
        )
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def _get_filtered_data(self, objects, serializer):
        try:
            user = self.context['request'].user
            queryset = filter_queryset_for_user(objects, user)
        except (KeyError, AttributeError):
            queryset = objects.all()

        serializer_instance = serializer(queryset, many=True, context=self.context)
        return serializer_instance.data

    def get_projects(self, obj):
        return self._get_filtered_data(obj.projects.all(), BasicProjectSerializer)

    def get_project_groups(self, obj):
        return self._get_filtered_data(obj.project_groups.all(), BasicProjectGroupSerializer)


class ProjectGroupSerializer(PermissionFieldFilteringMixin,
                             core_serializers.AugmentedSerializerMixin,
                             serializers.HyperlinkedModelSerializer):
    projects = serializers.SerializerMethodField()

    class Meta(object):
        model = models.ProjectGroup
        fields = (
            'url',
            'uuid',
            'name',
            'customer', 'customer_name', 'customer_native_name', 'customer_abbreviation',
            'projects',
            'description',
        )
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'customer': {'lookup_field': 'uuid'},
        }
        related_paths = {
            'customer': ('uuid', 'name', 'native_name', 'abbreviation')
        }

    def get_filtered_field_names(self):
        return 'customer',

    def get_fields(self):
        # TODO: Extract to a proper mixin
        fields = super(ProjectGroupSerializer, self).get_fields()

        try:
            method = self.context['view'].request.method
        except (KeyError, AttributeError):
            return fields

        if method in ('PUT', 'PATCH'):
            fields['customer'].read_only = True

        return fields

    def _get_filtered_data(self, objects, serializer):
        # XXX: this method completely duplicates _get_filtered_data in CustomerSerializer.
        # We need to create mixin to follow DRY principle. (NC-578)
        try:
            user = self.context['request'].user
            queryset = filter_queryset_for_user(objects, user)
        except (KeyError, AttributeError):
            queryset = objects.all()

        serializer_instance = serializer(queryset, many=True, context=self.context)
        return serializer_instance.data

    def get_projects(self, obj):
        return self._get_filtered_data(obj.projects.all(), BasicProjectSerializer)


class ProjectGroupMembershipSerializer(PermissionFieldFilteringMixin,
                                       serializers.HyperlinkedModelSerializer):
    project_group = serializers.HyperlinkedRelatedField(
        source='projectgroup',
        view_name='projectgroup-detail',
        lookup_field='uuid',
        queryset=models.ProjectGroup.objects.all(),
    )
    project_group_name = serializers.ReadOnlyField(source='projectgroup.name')
    project = serializers.HyperlinkedRelatedField(
        view_name='project-detail',
        lookup_field='uuid',
        queryset=models.Project.objects.all(),
    )
    project_name = serializers.ReadOnlyField(source='project.name')

    class Meta(object):
        model = models.ProjectGroup.projects.through
        fields = (
            'url',
            'project_group', 'project_group_name',
            'project', 'project_name',
        )
        view_name = 'projectgroup_membership-detail'

    def get_filtered_field_names(self):
        return 'project', 'project_group'


STRUCTURE_PERMISSION_USER_FIELDS = {
    'fields': ('user', 'user_full_name', 'user_native_name', 'user_username', 'user_uuid', 'user_email'),
    'path': ('username', 'full_name', 'native_name', 'uuid', 'email')
}


class CustomerPermissionSerializer(PermissionFieldFilteringMixin,
                                   core_serializers.AugmentedSerializerMixin,
                                   serializers.HyperlinkedModelSerializer):
    customer = serializers.HyperlinkedRelatedField(
        source='group.customerrole.customer',
        view_name='customer-detail',
        lookup_field='uuid',
        queryset=models.Customer.objects.all(),
    )

    role = MappedChoiceField(
        source='group.customerrole.role_type',
        choices=(
            ('owner', 'Owner'),
        ),
        choice_mappings={
            'owner': models.CustomerRole.OWNER,
        },
    )

    class Meta(object):
        model = User.groups.through
        fields = (
            'url', 'pk', 'role',
            'customer', 'customer_uuid', 'customer_name', 'customer_native_name', 'customer_abbreviation',
        ) + STRUCTURE_PERMISSION_USER_FIELDS['fields']
        related_paths = {
            'user': STRUCTURE_PERMISSION_USER_FIELDS['path'],
            'group.customerrole.customer': ('name', 'native_name', 'abbreviation', 'uuid')
        }
        extra_kwargs = {
            'user': {
                'view_name': 'user-detail',
                'lookup_field': 'uuid',
                'queryset': User.objects.all(),
            },
        }
        view_name = 'customer_permission-detail'

    def create(self, validated_data):
        customer = validated_data['customer']
        user = validated_data['user']
        role = validated_data['role']

        permission, _ = customer.add_user(user, role)

        return permission

    def to_internal_value(self, data):
        value = super(CustomerPermissionSerializer, self).to_internal_value(data)
        return {
            'user': value['user'],
            'customer': value['group']['customerrole']['customer'],
            'role': value['group']['customerrole']['role_type'],
        }

    def validate(self, data):
        customer = data['customer']
        user = data['user']
        role = data['role']

        if customer.has_user(user, role):
            raise serializers.ValidationError('The fields customer, user, role must make a unique set.')

        return data

    def get_filtered_field_names(self):
        return 'customer',


class ProjectPermissionSerializer(PermissionFieldFilteringMixin,
                                  core_serializers.AugmentedSerializerMixin,
                                  serializers.HyperlinkedModelSerializer):
    project = serializers.HyperlinkedRelatedField(
        source='group.projectrole.project',
        view_name='project-detail',
        lookup_field='uuid',
        queryset=models.Project.objects.all(),
    )

    role = MappedChoiceField(
        source='group.projectrole.role_type',
        choices=(
            ('admin', 'Administrator'),
            ('manager', 'Manager'),
        ),
        choice_mappings={
            'admin': models.ProjectRole.ADMINISTRATOR,
            'manager': models.ProjectRole.MANAGER,
        },
    )

    class Meta(object):
        model = User.groups.through
        fields = (
            'url', 'pk',
            'role',
            'project', 'project_uuid', 'project_name',
        ) + STRUCTURE_PERMISSION_USER_FIELDS['fields']

        related_paths = {
            'group.projectrole.project': ('name', 'uuid'),
            'user': STRUCTURE_PERMISSION_USER_FIELDS['path']
        }
        extra_kwargs = {
            'user': {
                'view_name': 'user-detail',
                'lookup_field': 'uuid',
                'queryset': User.objects.all(),
            },
        }
        view_name = 'project_permission-detail'

    def create(self, validated_data):
        project = validated_data['project']
        user = validated_data['user']
        role = validated_data['role']

        permission, _ = project.add_user(user, role)

        return permission

    def to_internal_value(self, data):
        value = super(ProjectPermissionSerializer, self).to_internal_value(data)
        return {
            'user': value['user'],
            'project': value['group']['projectrole']['project'],
            'role': value['group']['projectrole']['role_type'],
        }

    def validate(self, data):
        project = data['project']
        user = data['user']
        role = data['role']

        if project.has_user(user, role):
            raise serializers.ValidationError('The fields project, user, role must make a unique set.')

        return data

    def get_filtered_field_names(self):
        return 'project',


class ProjectGroupPermissionSerializer(PermissionFieldFilteringMixin,
                                       core_serializers.AugmentedSerializerMixin,
                                       serializers.HyperlinkedModelSerializer):
    project_group = serializers.HyperlinkedRelatedField(
        source='group.projectgrouprole.project_group',
        view_name='projectgroup-detail',
        lookup_field='uuid',
        queryset=models.ProjectGroup.objects.all(),
    )

    role = MappedChoiceField(
        source='group.projectgrouprole.role_type',
        choices=(
            ('manager', 'Manager'),
        ),
        choice_mappings={
            'manager': models.ProjectGroupRole.MANAGER,
        },
    )

    class Meta(object):
        model = User.groups.through
        fields = (
            'url', 'pk',
            'role',
            'project_group', 'project_group_uuid', 'project_group_name',
        ) + STRUCTURE_PERMISSION_USER_FIELDS['fields']
        related_paths = {
            'user': STRUCTURE_PERMISSION_USER_FIELDS['path'],
            'group.projectgrouprole.project_group': ('name', 'uuid'),
        }
        extra_kwargs = {
            'user': {
                'view_name': 'user-detail',
                'lookup_field': 'uuid',
                'queryset': User.objects.all(),
            },
        }
        view_name = 'projectgroup_permission-detail'

    def create(self, validated_data):
        project_group = validated_data['project_group']
        user = validated_data['user']
        role = validated_data['role']

        permission, _ = project_group.add_user(user, role)

        return permission

    def to_internal_value(self, data):
        value = super(ProjectGroupPermissionSerializer, self).to_internal_value(data)
        return {
            'user': value['user'],
            'project_group': value['group']['projectgrouprole']['project_group'],
            'role': value['group']['projectgrouprole']['role_type'],
        }

    def validate(self, data):
        project_group = data['project_group']
        user = data['user']
        role = data['role']

        if project_group.has_user(user, role):
            raise serializers.ValidationError('The fields project_group, user, role must make a unique set.')

        return data

    def get_filtered_field_names(self):
        return 'project_group',


class UserOrganizationSerializer(serializers.Serializer):
    organization = serializers.CharField(max_length=80)


class UserSerializer(serializers.HyperlinkedModelSerializer):
    email = serializers.EmailField()

    class Meta(object):
        model = User
        fields = (
            'url',
            'uuid', 'username',
            'full_name', 'native_name',
            'job_title', 'email', 'phone_number',
            'organization', 'organization_approved',
            'civil_number',
            'description',
            'is_staff', 'is_active',
        )
        read_only_fields = (
            'uuid',
            'civil_number',
            'organization',
            'organization_approved',
        )
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def get_fields(self):
        fields = super(UserSerializer, self).get_fields()

        try:
            request = self.context['view'].request
            user = request.user
        except (KeyError, AttributeError):
            return fields

        if not user.is_staff:
            del fields['is_active']
            del fields['is_staff']
            fields['description'].read_only = True

        if request.method in ('PUT', 'PATCH'):
            fields['username'].read_only = True

        return fields


class CreationTimeStatsSerializer(serializers.Serializer):
    MODEL_NAME_CHOICES = (('project', 'project'), ('customer', 'customer'), ('project_group', 'project_group'))
    MODEL_CLASSES = {'project': models.Project, 'customer': models.Customer, 'project_group': models.ProjectGroup}

    model_name = serializers.ChoiceField(choices=MODEL_NAME_CHOICES)
    start_timestamp = serializers.IntegerField(min_value=0)
    end_timestamp = serializers.IntegerField(min_value=0)
    segments_count = serializers.IntegerField(min_value=0)

    def get_stats(self, user):
        start_datetime = core_utils.timestamp_to_datetime(self.data['start_timestamp'])
        end_datetime = core_utils.timestamp_to_datetime(self.data['end_timestamp'])

        model = self.MODEL_CLASSES[self.data['model_name']]
        filtered_queryset = filters.filter_queryset_for_user(model.objects.all(), user)
        created_datetimes = (
            filtered_queryset
            .filter(created__gte=start_datetime, created__lte=end_datetime)
            .values('created')
            .annotate(count=django_models.Count('id', distinct=True)))

        time_and_value_list = [
            (core_utils.datetime_to_timestamp(dt['created']), dt['count']) for dt in created_datetimes]

        return core_utils.format_time_and_value_to_segment_list(
            time_and_value_list, self.data['segments_count'],
            self.data['start_timestamp'], self.data['end_timestamp'])


class PasswordSerializer(serializers.Serializer):
    password = serializers.CharField(min_length=7, validators=[
        RegexValidator(
            regex='\d',
            message='Ensure this field has at least one digit.',
        ),
        RegexValidator(
            regex='[a-zA-Z]',
            message='Ensure this field has at least one latin letter.',
        ),
    ])


class ServiceSettingsSerializer(PermissionFieldFilteringMixin,
                                core_serializers.AugmentedSerializerMixin,
                                serializers.HyperlinkedModelSerializer):

    customer_native_name = serializers.ReadOnlyField(source='customer.native_name')
    state = MappedChoiceField(
        choices=[(v, k) for k, v in core_models.SynchronizationStates.CHOICES],
        choice_mappings={v: k for k, v in core_models.SynchronizationStates.CHOICES},
        read_only=True)

    class Meta(object):
        model = models.ServiceSettings
        fields = (
            'url', 'uuid', 'name', 'type', 'state', 'shared',
            'backend_url', 'username', 'password', 'token',
            'customer', 'customer_name', 'customer_native_name',
            'dummy'
        )
        protected_fields = ('type', 'customer')
        read_only_fields = ('shared', 'state')
        write_only_fields = ('backend_url', 'username', 'token', 'password')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'customer': {'lookup_field': 'uuid'},
        }

    def get_filtered_field_names(self):
        return 'customer',

    def get_related_paths(self):
        return 'customer',

    def get_fields(self):
        fields = super(ServiceSettingsSerializer, self).get_fields()
        request = self.context['request']

        if isinstance(self.instance, self.Meta.model):
            perm = 'structure.change_%s' % self.Meta.model._meta.model_name
            if request.user.has_perms([perm], self.instance):
                for field in 'backend_url', 'username', 'token':
                    fields[field].write_only = False

        if request.method == 'GET':
            fields['type'] = serializers.ReadOnlyField(source='get_type_display')

        return fields


class BaseServiceSerializerMetaclass(serializers.SerializerMetaclass):
    TYPES = dict(models.ServiceSettings.Types.CHOICES)
    _get_list_view = staticmethod(lambda meta: meta.view_name.replace('-detail', '-list'))
    _get_model_str = staticmethod(lambda meta: force_text(meta.model._meta))


class ServiceSerializerMetaclass(BaseServiceSerializerMetaclass):
    """ Build a list of supported services via serializers definition.
        Example data structure.

        SUPPORTED_SERVICES = {
            'gitlab.gitlabservice': {
                'name': 'GitLab',
                'view_name': 'gitlab-list',
                'resources': {
                    'gitlab.group': {'name': 'Group', 'view_name': 'gitlab-group-list'},
                    'gitlab.project': {'name': 'Project', 'view_name': 'gitlab-project-list'},
                },
            },
        }
    """
    def __new__(cls, name, bases, args):
        service_type = args.get('SERVICE_TYPE', NotImplemented)
        if service_type is not NotImplemented:
            model_str = cls._get_model_str(args['Meta'])
            SUPPORTED_SERVICES.setdefault(model_str, {'resources': {}})
            SUPPORTED_SERVICES[model_str]['name'] = cls.TYPES[service_type]
            SUPPORTED_SERVICES[model_str]['view_name'] = cls._get_list_view(args['Meta'])
        return super(ServiceSerializerMetaclass, cls).__new__(cls, name, bases, args)


class BaseServiceSerializer(six.with_metaclass(ServiceSerializerMetaclass,
                            PermissionFieldFilteringMixin,
                            core_serializers.AugmentedSerializerMixin,
                            serializers.HyperlinkedModelSerializer)):

    SERVICE_TYPE = NotImplemented
    SERVICE_ACCOUNT_FIELDS = NotImplemented
    SERVICE_ACCOUNT_EXTRA_FIELDS = NotImplemented

    projects = BasicProjectSerializer(many=True, read_only=True)
    customer_native_name = serializers.ReadOnlyField(source='customer.native_name')
    settings = serializers.HyperlinkedRelatedField(
        queryset=models.ServiceSettings.objects.filter(shared=True),
        view_name='servicesettings-detail',
        lookup_field='uuid',
        allow_null=True)

    backend_url = serializers.CharField(max_length=200, allow_null=True, write_only=True, required=False)
    username = serializers.CharField(max_length=100, allow_null=True, write_only=True, required=False)
    password = serializers.CharField(max_length=100, allow_null=True, write_only=True, required=False)
    token = serializers.CharField(allow_null=True, write_only=True, required=False)
    dummy = serializers.BooleanField(write_only=True, required=False)

    class Meta(object):
        model = NotImplemented
        view_name = NotImplemented
        fields = (
            'uuid',
            'url',
            'name', 'projects',
            'customer', 'customer_name', 'customer_native_name',
            'settings', 'dummy',
            'backend_url', 'username', 'password', 'token',
        )
        protected_fields = (
            'customer', 'settings',
            'backend_url', 'username', 'password', 'token', 'dummy'
        )
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'customer': {'lookup_field': 'uuid'},
            'settings': {'lookup_field': 'uuid'},
        }

    def __new__(cls, *args, **kwargs):
        if cls.SERVICE_ACCOUNT_EXTRA_FIELDS is not NotImplemented:
            cls.Meta.fields += tuple(cls.SERVICE_ACCOUNT_EXTRA_FIELDS.keys())
        return super(BaseServiceSerializer, cls).__new__(cls, *args, **kwargs)

    def get_filtered_field_names(self):
        return 'customer',

    def get_related_paths(self):
        return 'customer',

    def get_fields(self):
        fields = super(BaseServiceSerializer, self).get_fields()
        if self.SERVICE_TYPE is not NotImplemented:
            fields['settings'].queryset = fields['settings'].queryset.filter(type=self.SERVICE_TYPE)

        if self.SERVICE_ACCOUNT_FIELDS is not NotImplemented:
            for field in ('backend_url', 'username', 'password', 'token'):
                if field in self.SERVICE_ACCOUNT_FIELDS:
                    fields[field].help_text = self.SERVICE_ACCOUNT_FIELDS[field]
                else:
                    del fields[field]

        return fields

    def build_unknown_field(self, field_name, model_class):
        if self.SERVICE_ACCOUNT_EXTRA_FIELDS is not NotImplemented:
            if field_name in self.SERVICE_ACCOUNT_EXTRA_FIELDS:
                return serializers.CharField, {
                    'write_only': True,
                    'required': False,
                    'allow_blank': True,
                    'help_text': self.SERVICE_ACCOUNT_EXTRA_FIELDS[field_name]}

        return super(BaseServiceSerializer, self).build_unknown_field(field_name, model_class)

    def validate_empty_values(self, data):
        # required=False is ignored for settings FK, deal with it here
        if 'settings' not in data:
            data['settings'] = None
        return super(BaseServiceSerializer, self).validate_empty_values(data)

    def validate(self, attrs):
        user = self.context['user']
        customer = attrs.get('customer') or self.instance.customer
        settings = attrs.get('settings')
        if not user.is_staff:
            if not customer.has_user(user, models.CustomerRole.OWNER):
                raise exceptions.PermissionDenied()
            if settings and not settings.shared and attrs.get('customer') != settings.customer:
                raise serializers.ValidationError('Customer must match settings customer.')

        if self.context['request'].method == 'POST':
            settings_fields = 'backend_url', 'username', 'password', 'token'
            create_settings = any([attrs.get(f) for f in settings_fields])
            if not settings and not create_settings:
                raise serializers.ValidationError(
                    "Either service settings or credentials must be supplied.")

            extra_fields = tuple()
            if self.SERVICE_ACCOUNT_EXTRA_FIELDS is not NotImplemented:
                extra_fields += tuple(self.SERVICE_ACCOUNT_EXTRA_FIELDS.keys())

            settings_fields += 'dummy',
            if create_settings:
                args = {f: attrs.get(f) for f in settings_fields if f in attrs}
                if extra_fields:
                    args['options'] = {f: attrs[f] for f in extra_fields if f in attrs}

                settings = models.ServiceSettings.objects.create(
                    type=self.SERVICE_TYPE,
                    name=attrs['name'],
                    customer=customer,
                    **args)

                send_task('structure', 'sync_service_settings')(settings.uuid.hex, initial=True)
                attrs['settings'] = settings

            for f in settings_fields + extra_fields:
                if f in attrs:
                    del attrs[f]

        return attrs


class BaseServiceProjectLinkSerializer(PermissionFieldFilteringMixin,
                                       core_serializers.AugmentedSerializerMixin,
                                       serializers.HyperlinkedModelSerializer):

    project = serializers.HyperlinkedRelatedField(
        queryset=models.Project.objects.all(),
        view_name='project-detail',
        lookup_field='uuid')

    state = MappedChoiceField(
        choices=[(v, k) for k, v in core_models.SynchronizationStates.CHOICES],
        choice_mappings={v: k for k, v in core_models.SynchronizationStates.CHOICES},
        read_only=True)

    class Meta(object):
        model = NotImplemented
        view_name = NotImplemented
        fields = (
            'url',
            'project', 'project_name', 'project_uuid',
            'service', 'service_name', 'service_uuid',
            'state',
        )
        extra_kwargs = {
            'service': {'lookup_field': 'uuid', 'view_name': NotImplemented},
        }

    def get_filtered_field_names(self):
        return 'project', 'service'

    def get_related_paths(self):
        return 'project', 'service'

    def validate(self, attrs):
        if attrs['service'].customer != attrs['project'].customer:
            raise serializers.ValidationError("Service customer doesn't match project customer")
        return attrs


class ResourceSerializerMetaclass(BaseServiceSerializerMetaclass):
    """ Build a list of supported resource via serializers definition.
        See ServiceSerializerMetaclass for details.
    """
    def __new__(cls, name, bases, args):
        service = args.get('service')
        if service and service.view_name is not NotImplemented:
            model_str = cls._get_model_str(args['Meta'])
            service_view = cls._get_list_view(service)
            for s in SUPPORTED_SERVICES:
                if SUPPORTED_SERVICES[s].get('view_name', '') == service_view:
                    SUPPORTED_SERVICES[s]['resources'].setdefault(model_str, {})
                    SUPPORTED_SERVICES[s]['resources'][model_str]['name'] = args['Meta'].model.__name__
                    SUPPORTED_SERVICES[s]['resources'][model_str]['view_name'] = cls._get_list_view(args['Meta'])
                    break
        return super(ResourceSerializerMetaclass, cls).__new__(cls, name, bases, args)


class BaseResourceSerializer(six.with_metaclass(ResourceSerializerMetaclass,
                             PermissionFieldFilteringMixin,
                             core_serializers.AugmentedSerializerMixin,
                             serializers.HyperlinkedModelSerializer)):

    state = serializers.ReadOnlyField(source='get_state_display')
    project_groups = BasicProjectGroupSerializer(
        source='service_project_link.project.project_groups', many=True, read_only=True)

    project = serializers.HyperlinkedRelatedField(
        source='service_project_link.project',
        view_name='project-detail',
        read_only=True,
        lookup_field='uuid')

    project_name = serializers.ReadOnlyField(source='service_project_link.project.name')
    project_uuid = serializers.ReadOnlyField(source='service_project_link.project.uuid')

    service_project_link = serializers.HyperlinkedRelatedField(
        view_name=NotImplemented,
        queryset=NotImplemented,
        write_only=True)

    service = serializers.HyperlinkedRelatedField(
        source='service_project_link.service',
        view_name=NotImplemented,
        read_only=True,
        lookup_field='uuid')

    service_name = serializers.ReadOnlyField(source='service_project_link.service.name')
    service_uuid = serializers.ReadOnlyField(source='service_project_link.service.uuid')

    customer = serializers.HyperlinkedRelatedField(
        source='service_project_link.project.customer',
        view_name='customer-detail',
        read_only=True,
        lookup_field='uuid')

    customer_name = serializers.ReadOnlyField(source='service_project_link.project.customer.name')
    customer_abbreviation = serializers.ReadOnlyField(source='service_project_link.project.customer.abbreviation')
    customer_native_name = serializers.ReadOnlyField(source='service_project_link.project.customer.native_name')

    created = serializers.DateTimeField(read_only=True)
    resource_type = serializers.SerializerMethodField()

    class Meta(object):
        model = NotImplemented
        view_name = NotImplemented
        fields = (
            'url', 'uuid', 'name', 'description', 'start_time',
            'service', 'service_name', 'service_uuid',
            'project', 'project_name', 'project_uuid',
            'customer', 'customer_name', 'customer_native_name', 'customer_abbreviation',
            'project_groups',
            'resource_type', 'state', 'created', 'service_project_link',
        )
        read_only_fields = ('start_time',)
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def get_filtered_field_names(self):
        return 'service_project_link',

    def get_resource_type(self, obj):
        return obj._meta.model.__name__

    def create(self, validated_data):
        data = validated_data.copy()
        fields = self.Meta.model._meta.get_all_field_names()
        # Remove `virtual` properties which ain't actually belong to the model
        for prop in data.keys():
            if prop not in fields:
                del data[prop]

        return super(BaseResourceSerializer, self).create(data)
