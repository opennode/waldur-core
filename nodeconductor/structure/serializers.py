from __future__ import unicode_literals

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib import auth

from rest_framework import serializers

from nodeconductor.structure import models
from rest_framework.exceptions import APIException


User = auth.get_user_model()

class CustomerSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Customer
        fields = ('url', 'name', 'abbreviation', 'contact_details')
        lookup_field = 'uuid'


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Project
        fields = ('url', 'name')
        lookup_field = 'uuid'


class ProjectGroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.ProjectGroup
        fields = ('url', 'name')
        lookup_field = 'uuid'


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


class ProjectPermissionReadSerializer(serializers.HyperlinkedModelSerializer):
    project = serializers.HyperlinkedRelatedField(source='group.projectrole.project', view_name='project-detail',
                                                  read_only=True, lookup_field='uuid')
    user = serializers.HyperlinkedRelatedField(view_name='user-detail', lookup_field='uuid',
                                               queryset=User.objects.all())

    role = ProjectRoleField(choices=models.ProjectRole.TYPE_CHOICES)

    def get_role_type(self, obj):
        return obj.group.projectrole.get_role_type_display()

    class Meta(object):
        model = User.groups.through
        fields = ('url', 'project', 'user', 'role')


class NotModifiedPermission(APIException):
    status_code = 304
    default_detail = 'Permissions were not modified'


class ProjectPermissionWriteSerializer(serializers.Serializer):
    project = serializers.HyperlinkedRelatedField(queryset=models.Project.objects.all(), view_name='project-detail',
                                                  lookup_field='uuid', source='group.projectrole.project')
    user = serializers.HyperlinkedRelatedField(view_name='user-detail', queryset=User.objects.all(),
                                                  lookup_field='uuid')

    role = ProjectRoleField(choices=models.ProjectRole.TYPE_CHOICES)

    class Meta(object):
        model = User.groups.through
        fields = ('project', 'user', 'role')

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


class UserSerializer(serializers.HyperlinkedModelSerializer):
    projects = serializers.SerializerMethodField('user_projects_roles')

    def user_projects_roles(self, obj):
        user_groups = obj.groups.through.objects.exclude(group__projectrole__project=None)
        project_metadata = []
        for g in user_groups:
            project_metadata.append({
            'role': models.ProjectRole.ROLE_TO_NAME[g.group.projectrole.role_type],
            'project': g.group.projectrole.project.name,
            'customer': g.group.projectrole.project.customer.name,
            'projectgroups': g.group.projectrole.project.project_groups.all().values_list('name', flat=True)
            })

        return project_metadata

    class Meta(object):
        model = User
        fields = ('uuid', 'username', 'first_name', 'last_name', 'projects')
        lookup_field = 'uuid'
