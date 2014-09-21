from __future__ import unicode_literals

from django.contrib import auth
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework import serializers
from rest_framework.exceptions import APIException
from rest_framework.reverse import reverse

from nodeconductor.core.serializers import PermissionFieldFilteringMixin, RelatedResourcesFieldMixin
from nodeconductor.structure import models


User = auth.get_user_model()


class BasicInfoSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        fields = ('url', 'name')
        lookup_field = 'uuid'


class BasicProjectSerializer(BasicInfoSerializer):
    class Meta(BasicInfoSerializer.Meta):
        model = models.Project


class BasicProjectGroupSerializer(BasicInfoSerializer):
    class Meta(BasicInfoSerializer.Meta):
        model = models.ProjectGroup


class ProjectSerializer(RelatedResourcesFieldMixin, serializers.HyperlinkedModelSerializer):
    project_groups = BasicProjectGroupSerializer(many=True, read_only=True)

    class Meta(object):
        model = models.Project
        fields = ('url', 'name', 'customer', 'customer_name', 'project_groups')
        lookup_field = 'uuid'

    def get_related_paths(self):
        return 'customer',


class ProjectCreateSerializer(PermissionFieldFilteringMixin,
                              serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Project
        fields = ('url', 'name', 'customer')
        lookup_field = 'uuid'

    def get_filtered_field_names(self):
        return 'customer',


class CustomerSerializer(serializers.HyperlinkedModelSerializer):
    projects = BasicProjectSerializer(many=True, read_only=True)
    project_groups = BasicProjectGroupSerializer(many=True, read_only=True)

    class Meta(object):
        model = models.Customer
        fields = ('url', 'name', 'abbreviation', 'contact_details', 'projects', 'project_groups')
        lookup_field = 'uuid'


class ProjectGroupSerializer(PermissionFieldFilteringMixin,
                             RelatedResourcesFieldMixin,
                             serializers.HyperlinkedModelSerializer):
    projects = BasicProjectSerializer(many=True, read_only=True)

    class Meta(object):
        model = models.ProjectGroup
        fields = ('url', 'name', 'customer', 'customer_name', 'projects')
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


class ProjectGroupMembershipSerializer(PermissionFieldFilteringMixin, serializers.HyperlinkedModelSerializer):
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


class ProjectPermissionReadSerializer(RelatedResourcesFieldMixin,
                                      serializers.HyperlinkedModelSerializer):
    user = serializers.HyperlinkedRelatedField(view_name='user-detail', lookup_field='uuid',
                                               queryset=User.objects.all())
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


class NotModifiedPermission(APIException):
    status_code = 304
    default_detail = 'Permissions were not modified'


class ProjectPermissionSerializer(PermissionFieldFilteringMixin,
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

    def save_object(self, obj, **kwargs):
        try:
            obj.save()
        except IntegrityError:
            raise NotModifiedPermission()

    def get_filtered_field_names(self):
        return 'project',


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
