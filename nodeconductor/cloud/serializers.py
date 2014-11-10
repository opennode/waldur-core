from rest_framework import serializers

from nodeconductor.cloud import models
from nodeconductor.core import serializers as core_serializers
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.serializers import BasicProjectSerializer


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


class CloudCreateSerializer(core_serializers.PermissionFieldFilteringMixin,
                            serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Cloud
        fields = ('uuid', 'url', 'name', 'customer', 'auth_url')

        lookup_field = 'uuid'

    def get_filtered_field_names(self):
        return 'customer',


class CloudSerializer(core_serializers.PermissionFieldFilteringMixin,
                      core_serializers.RelatedResourcesFieldMixin,
                      serializers.HyperlinkedModelSerializer):
    flavors = FlavorSerializer(many=True, read_only=True)
    projects = BasicProjectSerializer(many=True, read_only=True)

    class Meta(object):
        model = models.Cloud
        fields = ('uuid', 'url', 'name', 'customer', 'customer_name', 'flavors', 'projects')
        lookup_field = 'uuid'

    public_fields = ('uuid', 'url', 'name', 'customer', 'customer_name', 'flavors', 'projects')

    def get_filtered_field_names(self):
        return 'customer',

    def get_related_paths(self):
        return 'customer',

    def to_native(self, obj):
        # a workaround for DRF's webui bug
        if obj is None:
            return

        native = super(CloudSerializer, self).to_native(obj)
        try:
            user = self.context['request'].user
        except (KeyError, AttributeError):
            return native

        if not user.is_superuser:
            is_customer_owner = obj.customer.roles.filter(
                permission_group__user=user, role_type=structure_models.CustomerRole.OWNER).exists()
            if not is_customer_owner:
                for field_name in native:
                    if field_name not in self.public_fields:
                        del native[field_name]
        return native


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


class BasicSecurityGroupRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SecurityGroupRule
        fields = ('protocol', 'from_port', 'to_port', 'ip_range', 'netmask')


class SecurityGroupSerializer(serializers.HyperlinkedModelSerializer):

    rules = BasicSecurityGroupRuleSerializer(read_only=True)
    cloud_project_membership = CloudProjectMembershipSerializer()

    class Meta(object):
        model = models.SecurityGroup
        fields = ('url', 'uuid', 'name', 'description', 'rules',
                  'cloud_project_membership')
        lookup_field = 'uuid'
        view_name = 'security_group-detail'


class IpMappingSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = models.IpMapping
        fields = ('url', 'uuid', 'public_ip', 'private_ip', 'project')
        lookup_field = 'uuid'
        view_name = 'ip_mapping-detail'
