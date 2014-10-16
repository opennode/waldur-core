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
        fields = ('uuid', 'url', 'name', 'customer', 'customer_name', 'flavors', 'projects')
        lookup_field = 'uuid'

    public_fields = ('uuid', 'url', 'name')

    def __init__(self, *args, **kwargs):
        self.user = kwargs['context'].get('user', None)
        super(CloudSerializer, self).__init__(*args, **kwargs)

    def get_fields(self):
        fields = super(CloudSerializer, self).get_fields()
        is_customer_owner = self.object.customer.roles.filter(
            permission_group__user=self.user, role_type=structure_models.CustomerRole.OWNER).exists()
        if self.user is not None and not self.user.is_superuser and not is_customer_owner:
            return dict((key, value) for key, value in fields.iteritems() if key in self.public_fields)
        return fields

    def get_filtered_field_names(self):
        return 'customer',

    def get_related_paths(self):
        return 'customer',


class CloudProjectMembershipSerializer(core_serializers.PermissionFieldFilteringMixin,
                                       core_serializers.RelatedResourcesFieldMixin,
                                       serializers.HyperlinkedModelSerializer):

    class Meta(object):
        model = models.Cloud.projects.through
        fields = (
            'url',
            'project', 'project_name',
            'cloud', 'cloud_name',
        )
        view_name = 'projectcloud_membership-detail'

    def get_filtered_field_names(self):
        return 'project', 'cloud'

    def get_related_paths(self):
        return 'project', 'cloud'
