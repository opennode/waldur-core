from django.contrib.auth import get_user_model
from rest_framework import serializers

from nodeconductor.core.fields import MappedChoiceField
from nodeconductor.structure import models as structure_models
from nodeconductor.users import models

User = get_user_model()


class InvitationSerializer(serializers.HyperlinkedModelSerializer):
    project = serializers.HyperlinkedRelatedField(
        source='project_role.project',
        view_name='project-detail',
        lookup_field='uuid',
        queryset=structure_models.Project.objects.all(),
        required=False,
        allow_null=True
    )
    project_role = MappedChoiceField(
        source='project_role.role_type',
        choices=(
            ('admin', 'Administrator'),
            ('manager', 'Manager'),
        ),
        choice_mappings={
            'admin': structure_models.ProjectRole.ADMINISTRATOR,
            'manager': structure_models.ProjectRole.MANAGER,
        },
        required=False,
        allow_null=True
    )
    project_name = serializers.ReadOnlyField(source='project.name')
    customer = serializers.HyperlinkedRelatedField(
        source='customer_role.customer',
        view_name='customer-detail',
        lookup_field='uuid',
        queryset=structure_models.Customer.objects.all(),
        required=False,
        allow_null=True
    )
    customer_role = MappedChoiceField(
        source='customer_role.role_type',
        choices=(
            ('owner', 'Owner'),
        ),
        choice_mappings={
            'owner': structure_models.CustomerRole.OWNER,
        },
        required=False,
        allow_null=True
    )
    customer_name = serializers.ReadOnlyField(source='customer.name')

    expires = serializers.DateTimeField(source='get_expiration_time', read_only=True)

    class Meta(object):
        model = models.Invitation
        fields = ('url', 'uuid', 'link_template', 'email', 'civil_number',
                  'project', 'project_role', 'project_name',
                  'customer', 'customer_role', 'customer_name',
                  'state', 'error_message', 'created', 'expires')
        read_only_fields = ('url', 'uuid', 'state', 'error_message', 'created', 'expires')
        view_name = 'user-invitation-detail'
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def validate_email(self, email):
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError('User with provided email already exists.')

        return email

    def validate(self, attrs):
        link_template = attrs['link_template']
        if '{uuid}' not in link_template:
            raise serializers.ValidationError({'link_template': "Link template must include '{uuid}' parameter."})

        project_role = attrs.get('project_role', {})
        project = project_role.get('project')
        project_role_type = project_role.get('role_type')

        customer_role = attrs.get('customer_role', {})
        customer = customer_role.get('customer')
        customer_role_type = customer_role.get('role_type')

        if customer and project:
            raise serializers.ValidationError('Cannot create invitation to project and customer simultaneously.')
        elif not (customer or project):
            raise serializers.ValidationError('Customer or project must be provided.')
        elif (customer and customer_role_type is None) or (customer_role_type is not None and not customer):
            raise serializers.ValidationError({'customer_role': 'Customer and its role must be provided.'})
        elif (project and project_role_type is None) or (project_role_type is not None and not project):
            raise serializers.ValidationError({'project_role': 'Project and its role must be provided.'})

        return attrs

    def create(self, validated_data):
        project_role_data = validated_data.pop('project_role', {})
        project = project_role_data.get('project')
        customer_role_data = validated_data.pop('customer_role', {})
        customer = customer_role_data.get('customer')

        if project:
            project_role = project.roles.get(role_type=project_role_data['role_type'])
            validated_data['project_role'] = project_role
            validated_data['customer'] = project.customer
        elif customer:
            customer_role = customer.roles.get(role_type=customer_role_data['role_type'])
            validated_data['customer_role'] = customer_role
            validated_data['customer'] = customer

        return super(InvitationSerializer, self).create(validated_data)
