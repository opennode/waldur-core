from rest_framework import serializers

from nodeconductor.core.fields import MappedChoiceField
from nodeconductor.structure import models as structure_models
from nodeconductor.users import models


class InvitationSerializer(serializers.HyperlinkedModelSerializer):
    project = serializers.HyperlinkedRelatedField(
        source='project_role.project',
        view_name='project-detail',
        lookup_field='uuid',
        queryset=structure_models.Project.objects.all(),
    )

    role = MappedChoiceField(
        source='project_role.role_type',
        choices=(
            ('admin', 'Administrator'),
            ('manager', 'Manager'),
        ),
        choice_mappings={
            'admin': structure_models.ProjectRole.ADMINISTRATOR,
            'manager': structure_models.ProjectRole.MANAGER,
        },
    )

    class Meta(object):
        model = models.Invitation
        fields = ('url', 'uuid', 'state', 'link_template', 'email', 'project', 'role')
        read_only_fields = ('url', 'uuid', 'state')
        view_name = 'user-invitation-detail'
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def validate(self, attrs):
        link_template = attrs['link_template']

        if '{uuid}' not in link_template:
            raise serializers.ValidationError("Link template must include '{uuid}' parameter.")

        return attrs

    def create(self, validated_data):
        project_role_data = validated_data.pop('project_role')
        project_role = project_role_data['project'].roles.get(role_type=project_role_data['role_type'])
        validated_data['project_role'] = project_role

        return super(InvitationSerializer, self).create(validated_data)
