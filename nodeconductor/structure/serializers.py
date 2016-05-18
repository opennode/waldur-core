from __future__ import unicode_literals

from collections import defaultdict, OrderedDict

from django.conf import settings
from django.contrib import auth
from django.core.validators import RegexValidator, MaxLengthValidator
from django.db import models as django_models
from django.utils import six
from django.utils.functional import cached_property
from rest_framework import exceptions, serializers
from rest_framework.reverse import reverse

from nodeconductor.core import models as core_models
from nodeconductor.core import serializers as core_serializers
from nodeconductor.core import utils as core_utils
from nodeconductor.core.fields import MappedChoiceField
from nodeconductor.monitoring.serializers import MonitoringSerializerMixin
from nodeconductor.quotas import serializers as quotas_serializers
from nodeconductor.structure import (models, SupportedServices, ServiceBackendError, ServiceBackendNotImplemented,
                                     executors)
from nodeconductor.structure.managers import filter_queryset_for_user
from nodeconductor.structure.models import ServiceProjectLink

User = auth.get_user_model()


class IpCountValidator(MaxLengthValidator):
    message = 'Only %(limit_value)s ip address is supported.'


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
            field = fields[field_name]
            field.queryset = filter_queryset_for_user(field.queryset, user)

        return fields

    def get_filtered_field_names(self):
        raise NotImplementedError(
            'Implement get_filtered_field_names() '
            'to return list of filtered fields')


class PermissionListSerializer(serializers.ListSerializer):
    """
    Allows to filter related queryset by user.
    Counterpart of PermissionFieldFilteringMixin.

    In order to use it set Meta.list_serializer_class. Example:

    >>> class PermissionProjectGroupSerializer(BasicProjectGroupSerializer):
    >>>     class Meta(BasicProjectGroupSerializer.Meta):
    >>>         list_serializer_class = PermissionListSerializer
    >>>
    >>> class CustomerSerializer(serializers.HyperlinkedModelSerializer):
    >>>     project_groups = PermissionProjectGroupSerializer(many=True, read_only=True)
    """
    def to_representation(self, data):
        try:
            request = self.context['request']
            user = request.user
        except (KeyError, AttributeError):
            pass
        else:
            if isinstance(data, (django_models.Manager, django_models.query.QuerySet)):
                data = filter_queryset_for_user(data.all(), user)

        return super(PermissionListSerializer, self).to_representation(data)


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


class PermissionProjectSerializer(BasicProjectSerializer):
    class Meta(BasicProjectSerializer.Meta):
        list_serializer_class = PermissionListSerializer


class BasicProjectGroupSerializer(core_serializers.BasicInfoSerializer):
    class Meta(core_serializers.BasicInfoSerializer.Meta):
        model = models.ProjectGroup
        fields = ('url', 'name', 'uuid')
        read_only_fields = ('name', 'uuid')


class PermissionProjectGroupSerializer(BasicProjectGroupSerializer):
    class Meta(BasicProjectGroupSerializer.Meta):
        list_serializer_class = PermissionListSerializer


class NestedProjectGroupSerializer(core_serializers.HyperlinkedRelatedModelSerializer):
    class Meta(object):
        model = models.ProjectGroup
        fields = ('url', 'name', 'uuid')
        read_only_fields = ('name', 'uuid')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


class NestedServiceProjectLinkSerializer(serializers.Serializer):
    uuid = serializers.ReadOnlyField(source='service.uuid')
    url = serializers.SerializerMethodField()
    service_project_link_url = serializers.SerializerMethodField()
    name = serializers.ReadOnlyField(source='service.name')
    type = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    shared = serializers.SerializerMethodField()
    settings_uuid = serializers.ReadOnlyField(source='service.settings.uuid')
    settings = serializers.SerializerMethodField()

    def get_settings(self, link):
        """
        URL of service settings
        """
        return reverse(
            'servicesettings-detail', kwargs={'uuid': link.service.settings.uuid}, request=self.context['request'])

    def get_url(self, link):
        """
        URL of service
        """
        view_name = SupportedServices.get_detail_view_for_model(link.service)
        return reverse(view_name, kwargs={'uuid': link.service.uuid.hex}, request=self.context['request'])

    def get_service_project_link_url(self, link):
        view_name = SupportedServices.get_detail_view_for_model(link)
        return reverse(view_name, kwargs={'pk': link.id}, request=self.context['request'])

    def get_type(self, link):
        return SupportedServices.get_name_for_model(link.service)

    # XXX: SPL is intended to become stateless. For backward compatiblity we are returning here state from connected
    # service settings. To be removed once SPL becomes stateless.
    def get_state(self, link):
        return link.service.settings.get_state_display()

    def get_resources_count(self, link):
        """
        Count total number of all resources connected to link
        """
        total = 0
        for model in SupportedServices.get_service_resources(link.service):
            # Format query path from resource to service project link
            query = {model.Permissions.project_path.split('__')[0]: link}
            total += model.objects.filter(**query).count()
        return total

    def get_shared(self, link):
        return link.service.settings.shared


class ProjectSerializer(core_serializers.RestrictedSerializerMixin,
                        PermissionFieldFilteringMixin,
                        core_serializers.AugmentedSerializerMixin,
                        serializers.HyperlinkedModelSerializer):
    project_groups = NestedProjectGroupSerializer(
        queryset=models.ProjectGroup.objects.all(),
        many=True,
        required=False,
        default=(),
    )

    quotas = quotas_serializers.BasicQuotaSerializer(many=True, read_only=True)
    services = serializers.SerializerMethodField()

    class Meta(object):
        model = models.Project
        fields = (
            'url', 'uuid',
            'name',
            'customer', 'customer_uuid', 'customer_name', 'customer_native_name', 'customer_abbreviation',
            'project_groups',
            'description',
            'quotas',
            'services',
            'created',
        )
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'customer': {'lookup_field': 'uuid'},
        }
        related_paths = {
            'customer': ('uuid', 'name', 'native_name', 'abbreviation')
        }

    @staticmethod
    def eager_load(queryset):
        related_fields = (
            'uuid',
            'name',
            'created',
            'description',
            'customer__uuid',
            'customer__name',
            'customer__native_name',
            'customer__abbreviation'
        )
        return queryset.select_related('customer').only(*related_fields) \
            .prefetch_related('quotas', 'project_groups')

    def create(self, validated_data):
        project_groups = validated_data.pop('project_groups')
        project = super(ProjectSerializer, self).create(validated_data)
        project.project_groups.add(*project_groups)

        return project

    def get_filtered_field_names(self):
        return 'customer',

    def get_services(self, project):
        if 'services' not in self.context:
            self.context['services'] = self.get_services_map()
        services = self.context['services'][project.pk]

        serializer = NestedServiceProjectLinkSerializer(
            services,
            many=True,
            read_only=True,
            context={'request': self.context['request']})
        return serializer.data

    def get_services_map(self):
        services = defaultdict(list)
        related_fields = (
            'id',
            'service__settings__state',
            'project_id',
            'service__uuid',
            'service__name',
            'service__settings__uuid',
            'service__settings__shared'
        )
        for service in SupportedServices.get_service_models().values():
            link_model = service['service_project_link']
            links = link_model.objects.all()
            if not hasattr(link_model, 'cloud'):
                links = links.select_related('service', 'service__settings') \
                             .only(*related_fields)
            if isinstance(self.instance, list):
                links = links.filter(project__in=self.instance)
            else:
                links = links.filter(project=self.instance)
            for link in links:
                services[link.project_id].append(link)
        return services

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


class CustomerSerializer(core_serializers.RestrictedSerializerMixin,
                         core_serializers.AugmentedSerializerMixin,
                         serializers.HyperlinkedModelSerializer,):
    projects = PermissionProjectSerializer(many=True, read_only=True)
    project_groups = PermissionProjectGroupSerializer(many=True, read_only=True)
    owners = BasicUserSerializer(source='get_owners', many=True, read_only=True)
    image = DefaultImageField(required=False, read_only=True)
    quotas = quotas_serializers.BasicQuotaSerializer(many=True, read_only=True)

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
        # Balance should be modified by nodeconductor_paypal app
        read_only_fields = ('balance', )

    @staticmethod
    def eager_load(queryset):
        return queryset.prefetch_related('quotas', 'projects', 'project_groups')


class CustomerUserSerializer(serializers.ModelSerializer):
    role = serializers.ReadOnlyField(source='group.customerrole.get_role_type_display')
    permission = serializers.HyperlinkedRelatedField(
        source='perm.pk',
        view_name='customer_permission-detail',
        queryset=User.groups.through.objects.all(),
    )
    projects = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['url', 'uuid', 'username', 'full_name', 'role', 'permission', 'projects']
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def to_representation(self, user):
        customer = self.context['customer']
        try:
            group = user.groups.get(customerrole__customer=customer)
        except user.groups.model.DoesNotExist:
            group = None
            perm = None
        else:
            perm = User.groups.through.objects.get(user=user, group=group)

        setattr(user, 'group', group)
        setattr(user, 'perm', perm)
        return super(CustomerUserSerializer, self).to_representation(user)

    def get_projects(self, user):
        request = self.context['request']
        customer = self.context['customer']
        projectrole = {
            g.projectrole.project_id: (g.projectrole.get_role_type_display(),
                                       User.groups.through.objects.get(user=user, group=g).pk)
            for g in user.groups.exclude(projectrole=None)
        }
        projects = filter_queryset_for_user(
            models.Project.objects.filter(customer=customer).filter(id__in=projectrole.keys()), request.user)

        return [OrderedDict([
            ('url', reverse('project-detail', kwargs={'uuid': proj.uuid}, request=request)),
            ('uuid', proj.uuid),
            ('name', proj.name),
            ('role', projectrole[proj.id][0]),
            ('permission', reverse('project_permission-detail',
                                   kwargs={'pk': projectrole[proj.id][1]},
                                   request=request))
        ]) for proj in projects]


class BalanceHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.BalanceHistory
        fields = ['created', 'amount']


class ProjectGroupSerializer(PermissionFieldFilteringMixin,
                             core_serializers.AugmentedSerializerMixin,
                             serializers.HyperlinkedModelSerializer):
    projects = PermissionProjectSerializer(many=True, read_only=True)

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
        protected_fields = ('customer',)

    def get_filtered_field_names(self):
        return 'customer',


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
            'date_joined',
        )
        read_only_fields = (
            'uuid',
            'civil_number',
            'organization',
            'organization_approved',
            'date_joined',
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

    def validate(self, attrs):
        user = User(id=getattr(self.instance, 'id', None), **attrs)
        user.clean()
        return attrs


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
        filtered_queryset = filter_queryset_for_user(model.objects.all(), user)
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


class SshKeySerializer(serializers.HyperlinkedModelSerializer):
    user_uuid = serializers.ReadOnlyField(source='user.uuid')

    class Meta(object):
        model = core_models.SshPublicKey
        fields = ('url', 'uuid', 'name', 'public_key', 'fingerprint', 'user_uuid')
        read_only_fields = ('fingerprint',)
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def validate(self, attrs):
        try:
            fingerprint = core_models.get_ssh_key_fingerprint(attrs['public_key'])
        except (IndexError, TypeError):
            raise serializers.ValidationError('Key is not valid: cannot generate fingerprint from it.')
        if core_models.SshPublicKey.objects.filter(fingerprint=fingerprint).exists():
            raise serializers.ValidationError('Key with same fingerprint already exists')
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


class ServiceSettingsSerializer(PermissionFieldFilteringMixin,
                                core_serializers.AugmentedSerializerMixin,
                                serializers.HyperlinkedModelSerializer):

    customer_native_name = serializers.ReadOnlyField(source='customer.native_name')
    state = MappedChoiceField(
        choices=[(v, k) for k, v in core_models.SynchronizationStates.CHOICES],
        choice_mappings={v: k for k, v in core_models.SynchronizationStates.CHOICES},
        read_only=True)
    quotas = quotas_serializers.BasicQuotaSerializer(many=True, read_only=True)
    scope = core_serializers.GenericRelatedField(related_models=models.ResourceMixin.get_all_models(), required=False)

    class Meta(object):
        model = models.ServiceSettings
        fields = (
            'url', 'uuid', 'name', 'type', 'state', 'error_message', 'shared',
            'backend_url', 'username', 'password', 'token', 'certificate',
            'customer', 'customer_name', 'customer_native_name',
            'quotas', 'scope',
        )
        protected_fields = ('type', 'customer')
        read_only_fields = ('shared', 'state', 'error_message')
        write_only_fields = ('backend_url', 'username', 'token', 'password', 'certificate')
        related_paths = ('customer',)
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'customer': {'lookup_field': 'uuid'},
        }

    def get_filtered_field_names(self):
        return 'customer',

    def get_fields(self):
        fields = super(ServiceSettingsSerializer, self).get_fields()
        request = self.context['request']

        if isinstance(self.instance, self.Meta.model):
            perm = 'structure.change_%s' % self.Meta.model._meta.model_name
            if request.user.has_perms([perm], self.instance):
                # If user can change settings he should be able to see value
                for field in self.Meta.write_only_fields:
                    fields[field].write_only = False

                serializer = self.get_service_serializer()

                # Remove fields if they are not needed for service
                filter_fields = serializer.SERVICE_ACCOUNT_FIELDS
                if filter_fields is not NotImplemented:
                    for field in self.Meta.write_only_fields:
                        if field in filter_fields:
                            fields[field].help_text = filter_fields[field]
                        elif field in fields:
                            del fields[field]

                # Add extra fields stored in options dictionary
                extra_fields = serializer.SERVICE_ACCOUNT_EXTRA_FIELDS
                if extra_fields is not NotImplemented:
                    for field in extra_fields:
                        fields[field] = serializers.CharField(required=False,
                                                              source='options.' + field,
                                                              allow_blank=True,
                                                              help_text=extra_fields[field])

        if request.method == 'GET':
            fields['type'] = serializers.ReadOnlyField(source='get_type_display')

        return fields

    def get_service_serializer(self):
        service = SupportedServices.get_service_models()[self.instance.type]['service']
        # Find service serializer by service type of settings object
        return next(cls for cls in BaseServiceSerializer.__subclasses__()
                    if cls.Meta.model == service)


class ServiceSerializerMetaclass(serializers.SerializerMetaclass):
    """ Build a list of supported services via serializers definition.
        See SupportedServices for details.
    """
    def __new__(cls, name, bases, args):
        SupportedServices.register_service(args['Meta'].model)
        return super(ServiceSerializerMetaclass, cls).__new__(cls, name, bases, args)


class BaseServiceSerializer(six.with_metaclass(ServiceSerializerMetaclass,
                            PermissionFieldFilteringMixin,
                            core_serializers.AugmentedSerializerMixin,
                            serializers.HyperlinkedModelSerializer)):

    SERVICE_ACCOUNT_FIELDS = NotImplemented
    SERVICE_ACCOUNT_EXTRA_FIELDS = NotImplemented

    projects = BasicProjectSerializer(many=True, read_only=True)
    customer_native_name = serializers.ReadOnlyField(source='customer.native_name')
    settings = serializers.HyperlinkedRelatedField(
        queryset=models.ServiceSettings.objects.filter(shared=True),
        view_name='servicesettings-detail',
        lookup_field='uuid',
        allow_null=True)
    # if project is defined service will be automatically connected to projects customer
    # and SPL between service and project will be created
    project = serializers.HyperlinkedRelatedField(
        queryset=models.Project.objects.all(),
        view_name='project-detail',
        lookup_field='uuid',
        allow_null=True,
        required=False,
        write_only=True)

    backend_url = serializers.URLField(max_length=200, allow_null=True, write_only=True, required=False)
    username = serializers.CharField(max_length=100, allow_null=True, write_only=True, required=False)
    password = serializers.CharField(max_length=100, allow_null=True, write_only=True, required=False)
    token = serializers.CharField(allow_null=True, write_only=True, required=False)
    certificate = serializers.FileField(allow_null=True, write_only=True, required=False)
    resources_count = serializers.SerializerMethodField()
    service_type = serializers.SerializerMethodField()
    shared = serializers.ReadOnlyField(source='settings.shared')
    state = serializers.SerializerMethodField()
    error_message = serializers.ReadOnlyField(source='settings.error_message')
    scope = core_serializers.GenericRelatedField(related_models=models.Resource.get_all_models(), required=False)
    tags = serializers.SerializerMethodField()

    class Meta(object):
        model = NotImplemented
        view_name = NotImplemented
        fields = (
            'uuid',
            'url',
            'name', 'projects', 'project',
            'customer', 'customer_uuid', 'customer_name', 'customer_native_name',
            'settings', 'settings_uuid',
            'backend_url', 'username', 'password', 'token', 'certificate',
            'resources_count', 'service_type', 'shared', 'state', 'error_message',
            'available_for_all', 'scope', 'tags',
        )
        settings_fields = ('backend_url', 'username', 'password', 'token', 'certificate', 'scope')
        protected_fields = ('customer', 'settings', 'project') + settings_fields
        related_paths = ('customer', 'settings')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'customer': {'lookup_field': 'uuid'},
            'settings': {'lookup_field': 'uuid'},
        }

    def __new__(cls, *args, **kwargs):
        if cls.SERVICE_ACCOUNT_EXTRA_FIELDS is not NotImplemented:
            cls.Meta.fields += tuple(cls.SERVICE_ACCOUNT_EXTRA_FIELDS.keys())
            cls.Meta.protected_fields += tuple(cls.SERVICE_ACCOUNT_EXTRA_FIELDS.keys())
        return super(BaseServiceSerializer, cls).__new__(cls, *args, **kwargs)

    @staticmethod
    def eager_load(queryset):
        related_fields = (
            'uuid',
            'name',
            'available_for_all',
            'customer__uuid',
            'customer__name',
            'customer__native_name',
            'settings__state',
            'settings__uuid',
            'settings__type',
            'settings__shared',
            'settings__error_message',
            'settings__tags',
        )
        queryset = queryset.select_related('customer', 'settings').only(*related_fields)
        projects = models.Project.objects.all().only('uuid', 'name')
        return queryset.prefetch_related(django_models.Prefetch('projects', queryset=projects))

    def get_tags(self, service):
        return [t.name for t in service.settings.tags.all()]

    def get_filtered_field_names(self):
        return 'customer',

    def get_fields(self):
        fields = super(BaseServiceSerializer, self).get_fields()

        if self.Meta.model is not NotImplemented:
            key = SupportedServices.get_model_key(self.Meta.model)
            fields['settings'].queryset = fields['settings'].queryset.filter(type=key)

        if self.SERVICE_ACCOUNT_FIELDS is not NotImplemented:
            # each service settings could be connected to scope
            self.SERVICE_ACCOUNT_FIELDS['scope'] = 'VM that contains service'
            for field in self.Meta.settings_fields:
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
        project = attrs.get('project')
        if project and project.customer != customer:
            raise serializers.ValidationError(
                'Service cannot be connected to project that does not belong to services customer.')

        settings = attrs.get('settings')
        if not user.is_staff:
            if not customer.has_user(user, models.CustomerRole.OWNER):
                raise exceptions.PermissionDenied()
            if not self.instance and settings and not settings.shared:
                if attrs.get('customer') != settings.customer:
                    raise serializers.ValidationError('Customer must match settings customer.')

        if self.context['request'].method == 'POST':
            # Make shallow copy to protect from mutations
            settings_fields = self.Meta.settings_fields[:]
            create_settings = any([attrs.get(f) for f in settings_fields])
            if not settings and not create_settings:
                raise serializers.ValidationError(
                    "Either service settings or credentials must be supplied.")

            extra_fields = tuple()
            if self.SERVICE_ACCOUNT_EXTRA_FIELDS is not NotImplemented:
                extra_fields += tuple(self.SERVICE_ACCOUNT_EXTRA_FIELDS.keys())

            if create_settings:
                args = {f: attrs.get(f) for f in settings_fields if f in attrs}
                if extra_fields:
                    args['options'] = {f: attrs[f] for f in extra_fields if f in attrs}

                settings = models.ServiceSettings(
                    type=SupportedServices.get_model_key(self.Meta.model),
                    name=attrs['name'],
                    customer=customer,
                    **args)

                try:
                    backend = settings.get_backend()
                    backend.ping(raise_exception=True)
                except ServiceBackendError as e:
                    raise serializers.ValidationError("Wrong settings: %s" % e)
                except ServiceBackendNotImplemented:
                    pass

                settings.save()
                executors.ServiceSettingsCreateExecutor.execute(settings)
                attrs['settings'] = settings

            for f in settings_fields + extra_fields:
                if f in attrs:
                    del attrs[f]

        return attrs

    def get_resources_count(self, service):
        return self.get_resources_count_map[service.pk]

    @cached_property
    def get_resources_count_map(self):
        resource_models = SupportedServices.get_service_resources(self.Meta.model)
        counts = defaultdict(lambda: 0)
        user = self.context['request'].user
        for model in resource_models:
            service_path = model.Permissions.service_path
            if isinstance(self.instance, list):
                query = {service_path + '__in': self.instance}
            else:
                query = {service_path: self.instance}
            queryset = filter_queryset_for_user(model.objects.all(), user)
            rows = queryset.filter(**query).values(service_path)\
                .annotate(count=django_models.Count('id'))
            for row in rows:
                service_id = row[service_path]
                counts[service_id] += row['count']
        return counts

    def get_service_type(self, obj):
        return SupportedServices.get_name_for_model(obj)

    def get_state(self, obj):
        return obj.settings.get_state_display()

    def create(self, attrs):
        project = attrs.pop('project', None)
        service = super(BaseServiceSerializer, self).create(attrs)
        if project:
            spl = service.projects.through
            spl.objects.create(project=project, service=service)
        return service


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
            'service', 'service_name', 'service_uuid'
        )
        related_paths = ('project', 'service')
        extra_kwargs = {
            'service': {'lookup_field': 'uuid', 'view_name': NotImplemented},
        }

    def get_filtered_field_names(self):
        return 'project', 'service'

    def validate(self, attrs):
        if attrs['service'].customer != attrs['project'].customer:
            raise serializers.ValidationError("Service customer doesn't match project customer")

        # XXX: Consider adding unique key (service, project) to the model instead
        if self.Meta.model.objects.filter(service=attrs['service'], project=attrs['project']).exists():
            raise serializers.ValidationError("This service project link already exists")

        return attrs


class ResourceSerializerMetaclass(serializers.SerializerMetaclass):
    """ Build a list of supported resource via serializers definition.
        See SupportedServices for details.
    """
    def __new__(cls, name, bases, args):
        serializer = super(ResourceSerializerMetaclass, cls).__new__(cls, name, bases, args)
        SupportedServices.register_resource_serializer(args['Meta'].model, serializer)
        return serializer


class BasicResourceSerializer(serializers.Serializer):
    uuid = serializers.ReadOnlyField()
    name = serializers.ReadOnlyField()
    resource_type = serializers.SerializerMethodField()

    def get_resource_type(self, resource):
        return SupportedServices.get_name_for_model(resource)


class ManagedResourceSerializer(BasicResourceSerializer):
    project_name = serializers.ReadOnlyField(source='service_project_link.project.name')
    project_uuid = serializers.ReadOnlyField(source='service_project_link.project.uuid')

    customer_uuid = serializers.ReadOnlyField(source='service_project_link.project.customer.uuid')
    customer_name = serializers.ReadOnlyField(source='service_project_link.project.customer.name')


class RelatedResourceSerializer(BasicResourceSerializer):
    url = serializers.SerializerMethodField()
    service_tags = serializers.SerializerMethodField()

    def get_url(self, resource):
        return reverse(resource.get_url_name() + '-detail',
                       kwargs={'uuid': resource.uuid.hex},
                       request=self.context['request'])

    def get_service_tags(self, resource):
        spl = resource.service_project_link
        return [t.name for t in spl.service.settings.tags.all()]


class BaseResourceSerializer(six.with_metaclass(ResourceSerializerMetaclass,
                             core_serializers.RestrictedSerializerMixin,
                             MonitoringSerializerMixin,
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
        queryset=NotImplemented)

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

    tags = serializers.SerializerMethodField()
    access_url = serializers.SerializerMethodField()
    related_resources = RelatedResourceSerializer(source='get_related_resources', many=True, read_only=True)

    class Meta(object):
        model = NotImplemented
        view_name = NotImplemented
        fields = MonitoringSerializerMixin.Meta.fields + (
            'url', 'uuid', 'name', 'description', 'start_time',
            'service', 'service_name', 'service_uuid',
            'project', 'project_name', 'project_uuid',
            'customer', 'customer_name', 'customer_native_name', 'customer_abbreviation',
            'project_groups', 'tags', 'error_message',
            'resource_type', 'state', 'created', 'service_project_link', 'backend_id',
            'access_url', 'related_resources'
        )
        protected_fields = ('service', 'service_project_link')
        read_only_fields = ('start_time', 'error_message', 'backend_id')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def get_filtered_field_names(self):
        return 'service_project_link',

    def get_resource_type(self, obj):
        return SupportedServices.get_name_for_model(obj)

    def get_tags(self, obj):
        return [t.name for t in obj.tags.all()]

    def to_representation(self, instance):
        # We need this hook, because ips have to be represented as list
        if hasattr(instance, 'external_ips'):
            instance.external_ips = [instance.external_ips] if instance.external_ips else []
        if hasattr(instance, 'internal_ips'):
            instance.internal_ips = [instance.internal_ips] if instance.internal_ips else []
        return super(BaseResourceSerializer, self).to_representation(instance)

    def get_resource_fields(self):
        return self.Meta.model._meta.get_all_field_names()

    # an optional generic URL for accessing a resource
    def get_access_url(self, obj):
        return obj.get_access_url()

    def create(self, validated_data):
        data = validated_data.copy()
        fields = self.get_resource_fields()
        # Remove `virtual` properties which ain't actually belong to the model
        for prop in data.keys():
            if prop not in fields:
                del data[prop]

        return super(BaseResourceSerializer, self).create(data)


class PublishableResourceSerializer(BaseResourceSerializer):

    class Meta(BaseResourceSerializer.Meta):
        fields = BaseResourceSerializer.Meta.fields + ('publishing_state',)
        read_only_fields = BaseResourceSerializer.Meta.read_only_fields + ('publishing_state',)


class SummaryResourceSerializer(serializers.Serializer):

    def to_representation(self, instance):
        serializer = SupportedServices.get_resource_serializer(instance.__class__)
        return serializer(instance, context=self.context).data


class BaseResourceImportSerializer(PermissionFieldFilteringMixin,
                                   serializers.HyperlinkedModelSerializer):

    backend_id = serializers.CharField(write_only=True)
    project = serializers.HyperlinkedRelatedField(
        queryset=models.Project.objects.all(),
        view_name='project-detail',
        lookup_field='uuid',
        write_only=True)

    state = serializers.ReadOnlyField(source='get_state_display')
    created = serializers.DateTimeField(read_only=True)

    class Meta(object):
        model = NotImplemented
        view_name = NotImplemented
        fields = (
            'url', 'uuid', 'name', 'state', 'created',
            'backend_id', 'project'
        )
        read_only_fields = ('name',)
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def get_filtered_field_names(self):
        return 'project',

    def get_fields(self):
        fields = super(BaseResourceImportSerializer, self).get_fields()
        fields['project'].queryset = self.context['service'].projects.all()
        return fields

    def validate(self, attrs):
        if self.Meta.model.objects.filter(backend_id=attrs['backend_id']).exists():
            raise serializers.ValidationError(
                {'backend_id': "This resource is already linked to NodeConductor"})

        spl_class = SupportedServices.get_related_models(self.Meta.model)['service_project_link']
        spl = spl_class.objects.get(service=self.context['service'], project=attrs['project'])
        attrs['service_project_link'] = spl

        return attrs

    def create(self, validated_data):
        validated_data.pop('project')
        return super(BaseResourceImportSerializer, self).create(validated_data)


class VirtualMachineSerializer(BaseResourceSerializer):

    external_ips = serializers.ListField(
        child=core_serializers.IPAddressField(),
        read_only=True,
    )
    internal_ips = serializers.ListField(
        child=core_serializers.IPAddressField(),
        read_only=True,
    )

    ssh_public_key = serializers.HyperlinkedRelatedField(
        view_name='sshpublickey-detail',
        lookup_field='uuid',
        queryset=core_models.SshPublicKey.objects.all(),
        required=False,
        write_only=True)

    class Meta(BaseResourceSerializer.Meta):
        fields = BaseResourceSerializer.Meta.fields + (
            'cores', 'ram', 'disk', 'min_ram', 'min_disk',
            'ssh_public_key', 'user_data', 'external_ips', 'internal_ips',
            'latitude', 'longitude', 'key_name', 'key_fingerprint', 'image_name'
        )
        read_only_fields = BaseResourceSerializer.Meta.read_only_fields + (
            'cores', 'ram', 'disk', 'min_ram', 'min_disk',
            'external_ips', 'internal_ips',
            'latitude', 'longitude', 'key_name', 'key_fingerprint', 'image_name'
        )
        protected_fields = BaseResourceSerializer.Meta.protected_fields + (
            'user_data', 'ssh_public_key'
        )

    def get_fields(self):
        fields = super(VirtualMachineSerializer, self).get_fields()
        if 'ssh_public_key' in fields:
            fields['ssh_public_key'].queryset = fields['ssh_public_key'].queryset.filter(
                user=self.context['request'].user)
        return fields

    def create(self, validated_data):
        validated_data['image_name'] = validated_data['image'].name
        return super(VirtualMachineSerializer, self).create(validated_data)


class PropertySerializerMetaclass(serializers.SerializerMetaclass):
    """ Build a list of supported properties via serializers definition.
        See SupportedServices for details.
    """
    def __new__(cls, name, bases, args):
        SupportedServices.register_property(args['Meta'].model)
        return super(PropertySerializerMetaclass, cls).__new__(cls, name, bases, args)


class BasePropertySerializer(six.with_metaclass(PropertySerializerMetaclass,
                             serializers.HyperlinkedModelSerializer)):

    class Meta(object):
        model = NotImplemented


class AggregateSerializer(serializers.Serializer):
    MODEL_NAME_CHOICES = (
        ('project', 'project'),
        ('customer', 'customer'),
        ('project_group', 'project_group')
    )
    MODEL_CLASSES = {
        'project': models.Project,
        'customer': models.Customer,
        'project_group': models.ProjectGroup,
    }

    aggregate = serializers.ChoiceField(choices=MODEL_NAME_CHOICES, default='customer')
    uuid = serializers.CharField(allow_null=True, default=None)

    def get_aggregates(self, user):
        model = self.MODEL_CLASSES[self.data['aggregate']]
        queryset = filter_queryset_for_user(model.objects.all(), user)

        if 'uuid' in self.data and self.data['uuid']:
            queryset = queryset.filter(uuid=self.data['uuid'])
        return queryset

    def get_projects(self, user):
        queryset = self.get_aggregates(user)

        if self.data['aggregate'] == 'project':
            return queryset.all()
        elif self.data['aggregate'] == 'project_group':
            queryset = models.Project.objects.filter(project_groups__in=list(queryset))
            return filter_queryset_for_user(queryset, user)
        else:
            queryset = models.Project.objects.filter(customer__in=list(queryset))
            return filter_queryset_for_user(queryset, user)

    def get_service_project_links(self, user):
        projects = self.get_projects(user)
        return [model.objects.filter(project__in=projects)
                for model in ServiceProjectLink.get_all_models()]
