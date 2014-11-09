from __future__ import unicode_literals

from django.contrib import auth
from django.core.exceptions import ValidationError
from rest_framework import serializers
from rest_framework.reverse import reverse

from nodeconductor.core import serializers as core_serializers
from nodeconductor.structure import models
from nodeconductor.structure.filters import filter_queryset_for_user


User = auth.get_user_model()


class BasicUserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = User
        fields = ('url', 'uuid', 'username', 'full_name', 'native_name',)
        lookup_field = 'uuid'


class BasicProjectSerializer(core_serializers.BasicInfoSerializer):
    class Meta(core_serializers.BasicInfoSerializer.Meta):
        model = models.Project


class BasicProjectGroupSerializer(core_serializers.BasicInfoSerializer):
    class Meta(core_serializers.BasicInfoSerializer.Meta):
        model = models.ProjectGroup


class ResourceQuotaSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = models.ResourceQuota
        fields = ('vcpu', 'ram', 'storage', 'max_instances')


class ProjectSerializer(core_serializers.CollectedFieldsMixin,
                        core_serializers.RelatedResourcesFieldMixin,
                        serializers.HyperlinkedModelSerializer):
    project_groups = BasicProjectGroupSerializer(many=True, read_only=True)
    resource_quota = ResourceQuotaSerializer(read_only=True)
    resource_quota_usage = ResourceQuotaSerializer(read_only=True)

    class Meta(object):
        model = models.Project
        fields = ('url', 'uuid', 'name', 'customer', 'customer_name', 'project_groups', 'resource_quota',
                  'resource_quota_usage')
        lookup_field = 'uuid'

    def get_related_paths(self):
        return 'customer',


class ProjectCreateSerializer(core_serializers.PermissionFieldFilteringMixin,
                              serializers.HyperlinkedModelSerializer):

    resource_quota = ResourceQuotaSerializer(required=False)

    class Meta(object):
        model = models.Project
        fields = ('url', 'name', 'customer', 'resource_quota', 'project_groups')
        lookup_field = 'uuid'

    def get_filtered_field_names(self):
        return 'customer',

    def validate(self, attrs):
        try:
            user = self.context['request'].user
        except (KeyError, AttributeError):
            return attrs

        if user.is_staff:
            return attrs
        is_customer_owner = attrs['customer'].roles.filter(
            permission_group__user=user, role_type=models.CustomerRole.OWNER).exists()
        if is_customer_owner:
            return attrs

        groups = attrs['project_groups']
        if not groups:
            raise ValidationError('Project has to belong to some group')

        for group in groups:
            is_group_manager = group.roles.filter(
                permission_group__user=user, role_type=models.ProjectGroupRole.MANAGER).exists()
            if not is_group_manager:
                raise ValidationError('User does not have permission to add project to %s' % group)

        return attrs


class CustomerSerializer(core_serializers.CollectedFieldsMixin,
                         serializers.HyperlinkedModelSerializer):
    projects = serializers.SerializerMethodField('get_customer_projects')
    project_groups = serializers.SerializerMethodField('get_customer_project_groups')
    owners = BasicUserSerializer(source='get_owners', many=True, read_only=True)

    class Meta(object):
        model = models.Customer
        fields = ('url', 'uuid', 'name', 'abbreviation', 'contact_details', 'projects', 'project_groups', 'owners')
        lookup_field = 'uuid'

    def _get_filtered_data(self, objects, serializer):
        try:
            user = self.context['request'].user
        except (KeyError, AttributeError):
            return None

        queryset = filter_queryset_for_user(objects, user)
        serializer_instance = serializer(queryset, context={'request': self.context['request']})
        return serializer_instance.data

    def get_customer_projects(self, obj):
        return self._get_filtered_data(obj.projects.all(), BasicProjectSerializer)

    def get_customer_project_groups(self, obj):
        return self._get_filtered_data(obj.project_groups.all(), BasicProjectGroupSerializer)


class ProjectGroupSerializer(core_serializers.PermissionFieldFilteringMixin,
                             core_serializers.RelatedResourcesFieldMixin,
                             serializers.HyperlinkedModelSerializer):
    projects = BasicProjectSerializer(many=True, read_only=True)

    class Meta(object):
        model = models.ProjectGroup
        fields = ('url', 'uuid', 'name', 'customer', 'customer_name', 'projects')
        lookup_field = 'uuid'

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

    def get_related_paths(self):
        return 'customer',


class ProjectGroupMembershipSerializer(core_serializers.PermissionFieldFilteringMixin,
                                       serializers.HyperlinkedModelSerializer):
    project_group = serializers.HyperlinkedRelatedField(
        source='projectgroup',
        view_name='projectgroup-detail',
        lookup_field='uuid',
    )
    project_group_name = serializers.Field(source='projectgroup.name')
    project = serializers.HyperlinkedRelatedField(
        view_name='project-detail',
        lookup_field='uuid',
    )
    project_name = serializers.Field(source='project.name')

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


class ProjectRoleField(serializers.ChoiceField):

    def field_to_native(self, obj, field_name):
        if obj is not None:
            return models.ProjectRole.ROLE_TO_NAME[obj.group.projectrole.role_type]

    def field_from_native(self, data, files, field_name, into):
        role = data.get('role')
        if role in models.ProjectRole.NAME_TO_ROLE:
            into[field_name] = models.ProjectRole.NAME_TO_ROLE[role]
        else:
            raise ValidationError('Unknown role')


class ProjectGroupRoleField(serializers.ChoiceField):

    def field_to_native(self, obj, field_name):
        if obj is not None:
            return models.ProjectGroupRole.ROLE_TO_NAME[obj.group.projectgrouprole.role_type]

    def field_from_native(self, data, files, field_name, into):
        role = data.get('role')
        if role in models.ProjectGroupRole.NAME_TO_ROLE:
            into[field_name] = models.ProjectGroupRole.NAME_TO_ROLE[role]
        else:
            raise ValidationError('Unknown role')


class CustomerRoleField(serializers.ChoiceField):

    def field_to_native(self, obj, field_name):
        if obj is not None:
            return models.CustomerRole.ROLE_TO_NAME[obj.group.customerrole.role_type]

    def field_from_native(self, data, files, field_name, into):
        role = data.get('role')
        if role in models.CustomerRole.NAME_TO_ROLE:
            into[field_name] = models.CustomerRole.NAME_TO_ROLE[role]
        else:
            raise ValidationError('Unknown role')


class ProjectPermissionReadSerializer(core_serializers.RelatedResourcesFieldMixin,
                                      serializers.HyperlinkedModelSerializer):
    user = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        lookup_field='uuid',
        queryset=User.objects.all(),
    )
    user_full_name = serializers.Field(source='user.full_name')
    user_native_name = serializers.Field(source='user.native_name')

    role = ProjectRoleField(choices=models.ProjectRole.TYPE_CHOICES)

    class Meta(object):
        model = User.groups.through
        fields = (
            'url',
            'project', 'project_name',
            'user', 'user_full_name', 'user_native_name',
            'role',
        )
        view_name = 'project_permission-detail'

    def get_related_paths(self):
        return 'group.projectrole.project',


# TODO: refactor to abstract class, subclass by CustomerPermissions and ProjectPermissions
class CustomerPermissionSerializer(core_serializers.PermissionFieldFilteringMixin,
                                   serializers.HyperlinkedModelSerializer):
    customer = serializers.HyperlinkedRelatedField(
        source='group.customerrole.customer',
        view_name='customer-detail',
        lookup_field='uuid',
        queryset=models.Customer.objects.all(),
    )
    customer_name = serializers.Field(source='group.customerrole.customer.name')

    user = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        lookup_field='uuid',
        queryset=User.objects.all(),
    )
    user_full_name = serializers.Field(source='user.full_name')
    user_native_name = serializers.Field(source='user.native_name')
    user_username = serializers.Field(source='user.username')

    role = CustomerRoleField(choices=models.CustomerRole.TYPE_CHOICES)

    class Meta(object):
        model = User.groups.through
        fields = (
            'url', 'role',
            'customer', 'customer_name',
            'user', 'user_username', 'user_full_name', 'user_native_name',
        )
        view_name = 'customer_permission-detail'

    def restore_object(self, attrs, instance=None):
        customer = attrs['group.customerrole.customer']
        group = customer.roles.get(role_type=attrs['role']).permission_group
        UserGroup = User.groups.through
        return UserGroup(user=attrs['user'], group=group)

    def get_filtered_field_names(self):
        return 'customer',


class ProjectPermissionSerializer(core_serializers.PermissionFieldFilteringMixin,
                                  serializers.HyperlinkedModelSerializer):
    project = serializers.HyperlinkedRelatedField(source='group.projectrole.project', view_name='project-detail',
                                                  lookup_field='uuid', queryset=models.Project.objects.all())
    user = serializers.HyperlinkedRelatedField(view_name='user-detail', lookup_field='uuid',
                                               queryset=User.objects.all())

    project_name = serializers.Field(source='group.projectrole.project.name')
    user_full_name = serializers.Field(source='user.full_name')
    user_native_name = serializers.Field(source='user.native_name')

    role = ProjectRoleField(choices=models.ProjectRole.TYPE_CHOICES)

    class Meta(object):
        model = User.groups.through
        fields = (
            'url',
            'role',
            'project', 'project_name',
            'user', 'user_full_name', 'user_native_name',
        )
        view_name = 'project_permission-detail'

    def restore_object(self, attrs, instance=None):
        project = attrs['group.projectrole.project']
        group = project.roles.get(role_type=attrs['role']).permission_group
        UserGroup = User.groups.through
        return UserGroup(user=attrs['user'], group=group)

    def get_filtered_field_names(self):
        return 'project',


class ProjectGroupPermissionSerializer(core_serializers.PermissionFieldFilteringMixin,
                                       serializers.HyperlinkedModelSerializer):
    project_group = serializers.HyperlinkedRelatedField(source='group.projectgrouprole.project_group', view_name='projectgroup-detail',
                                                        lookup_field='uuid', queryset=models.ProjectGroup.objects.all())
    user = serializers.HyperlinkedRelatedField(view_name='user-detail', lookup_field='uuid',
                                               queryset=User.objects.all())

    project_group_name = serializers.Field(source='group.projectgrouprole.project_group.name')
    user_full_name = serializers.Field(source='user.full_name')
    user_native_name = serializers.Field(source='user.native_name')

    role = ProjectGroupRoleField(choices=models.ProjectGroupRole.TYPE_CHOICES)

    class Meta(object):
        model = User.groups.through
        fields = (
            'url',
            'role',
            'project_group', 'project_group_name',
            'user', 'user_full_name', 'user_native_name',
        )
        view_name = 'projectgroup_permission-detail'

    def restore_object(self, attrs, instance=None):
        project_group = attrs['group.projectgrouprole.project_group']
        group = project_group.roles.get(role_type=attrs['role']).permission_group
        UserGroup = User.groups.through
        return UserGroup(user=attrs['user'], group=group)

    def save_object(self, obj, **kwargs):
        try:
            obj.save()
        except IntegrityError:
            raise NotModifiedPermission()

    def get_filtered_field_names(self):
        return 'project_group',


class UserSerializer(serializers.HyperlinkedModelSerializer):
    project_groups = serializers.SerializerMethodField('user_project_groups')
    email = serializers.EmailField()

    def user_project_groups(self, obj):
        request = self.context.get('request')

        project_groups_qs = models.ProjectGroup.objects.filter(
            projects__roles__permission_group__user=obj).distinct()

        return [
            {
                'url': reverse('projectgroup-detail', kwargs={'uuid': project_group['uuid']}, request=request),
                'name': project_group['name'],
            }
            for project_group in
            project_groups_qs.values('uuid', 'name').iterator()
        ]

    class Meta(object):
        model = User
        fields = ('url', 'uuid', 'username', 'full_name', 'native_name', 'job_title', 'email',
                  'civil_number', 'phone_number', 'description', 'is_staff', 'organization', 'project_groups')
        read_only_fields = ('uuid', 'is_staff')
        lookup_field = 'uuid'
