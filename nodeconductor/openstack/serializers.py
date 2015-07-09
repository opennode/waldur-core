from rest_framework import serializers

from nodeconductor.structure import models as structure_models
from nodeconductor.structure import serializers as structure_serializers
from nodeconductor.openstack import models


class FlavorSerializer(serializers.HyperlinkedModelSerializer):

    class Meta(object):
        model = models.Flavor
        view_name = 'openstack-flavor-detail'
        fields = ('url', 'uuid', 'name')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


class ImageSerializer(serializers.HyperlinkedModelSerializer):

    class Meta(object):
        model = models.Image
        view_name = 'openstack-image-detail'
        fields = ('url', 'uuid', 'name')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


class ServiceSerializer(structure_serializers.BaseServiceSerializer):

    SERVICE_TYPE = structure_models.ServiceSettings.Types.OpenStack
    SERVICE_ACCOUNT_FIELDS = {
        'backend_url': 'Keystone auth URL (e.g. http://keystone.example.com:5000/v2.0)',
        'username': 'Administrative user',
        'password': '',
    }
    SERVICE_ACCOUNT_EXTRA_FIELDS = {
        'tenant_name': 'Administrative tenant (default: "admin")',
        'availability_zone': 'Default availability zone for provisioned Instances',
        'cpu_overcommit_ratio': '(default: 1)',
    }

    class Meta(structure_serializers.BaseServiceSerializer.Meta):
        model = models.OpenStackService
        view_name = 'openstack-detail'


class ServiceProjectLinkSerializer(structure_serializers.BaseServiceProjectLinkSerializer):

    class Meta(structure_serializers.BaseServiceProjectLinkSerializer.Meta):
        model = models.OpenStackServiceProjectLink
        view_name = 'openstack-spl-detail'
        extra_kwargs = {
            'service': {'lookup_field': 'uuid', 'view_name': 'openstack-detail'},
        }
