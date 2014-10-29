from django.core.paginator import Page

from rest_framework import serializers

from nodeconductor.core import serializers as core_serializers
from nodeconductor.cloud import models
from nodeconductor.structure.serializers import BasicProjectSerializer
from nodeconductor.structure import models as structure_models


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
    projects = BasicProjectSerializer(many=True, read_only=True)

    class Meta(object):
        model = models.Cloud
        fields = ('uuid', 'url', 'name', 'customer', 'customer_name', 'flavors', 'projects', 'username')
        lookup_field = 'uuid'

    public_fields = ('uuid', 'url', 'name', 'customer', 'customer_name', 'flavors', 'projects')

    def __init__(self, *args, **kwargs):
        self.user = kwargs['context'].get('user', None)
        super(CloudSerializer, self).__init__(*args, **kwargs)

    def get_filtered_field_names(self):
        return 'customer',

    def get_related_paths(self):
        return 'customer',

    def to_native(self, obj):
        """
        Serializer returns only public fields for non-customer owner
        """
        # a workaround for DRF's webui bug
        if obj is None:
            return
        native = super(CloudSerializer, self).to_native(obj)
        is_customer_owner = obj.customer.roles.filter(
            permission_group__user=self.user, role_type=structure_models.CustomerRole.OWNER).exists()
        if self.user is not None and not self.user.is_superuser and not is_customer_owner:
            return dict((key, value) for key, value in native.iteritems() if key in self.public_fields)
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


class SecurityGroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.SecurityGroup
        fields = ('url', 'uuid', 'name', 'description', 'protocol',
                  'from_port', 'to_port', 'ip_range', 'netmask')
        lookup_field = 'uuid'
        view_name = 'security_group-detail'
