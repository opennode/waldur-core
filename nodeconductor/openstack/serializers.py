from django.db.models import Max
from django.core.validators import MaxLengthValidator

from rest_framework import serializers

from nodeconductor.core import models as core_models
from nodeconductor.core import serializers as core_serializers
from nodeconductor.structure import SupportedServices, serializers as structure_serializers
from nodeconductor.openstack import models


class FlavorSerializer(serializers.HyperlinkedModelSerializer):

    class Meta(object):
        model = models.Flavor
        view_name = 'openstack-flavor-detail'
        fields = ('url', 'uuid', 'name', 'cores', 'ram', 'disk')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


class ImageSerializer(serializers.HyperlinkedModelSerializer):

    class Meta(object):
        model = models.Image
        view_name = 'openstack-image-detail'
        fields = ('url', 'uuid', 'name', 'min_disk', 'min_ram')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


class ServiceSerializer(structure_serializers.BaseServiceSerializer):

    SERVICE_TYPE = SupportedServices.Types.OpenStack
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
        model = models.Service
        view_name = 'openstack-detail'


class ServiceProjectLinkSerializer(structure_serializers.BaseServiceProjectLinkSerializer):

    class Meta(structure_serializers.BaseServiceProjectLinkSerializer.Meta):
        model = models.ServiceProjectLink
        view_name = 'openstack-spl-detail'
        extra_kwargs = {
            'service': {'lookup_field': 'uuid', 'view_name': 'openstack-detail'},
        }


class IpCountValidator(MaxLengthValidator):
    message = 'Only %(limit_value)s ip address is supported.'


class InstanceSerializer(structure_serializers.BaseResourceSerializer):

    service = serializers.HyperlinkedRelatedField(
        source='service_project_link.service',
        view_name='openstack-detail',
        read_only=True,
        lookup_field='uuid')

    service_project_link = serializers.HyperlinkedRelatedField(
        view_name='openstack-spl-detail',
        queryset=models.ServiceProjectLink.objects.all(),
        write_only=True)

    flavor = serializers.HyperlinkedRelatedField(
        view_name='openstack-flavor-detail',
        lookup_field='uuid',
        queryset=models.Flavor.objects.all().select_related('settings'),
        write_only=True)

    image = serializers.HyperlinkedRelatedField(
        view_name='openstack-image-detail',
        lookup_field='uuid',
        queryset=models.Image.objects.all().select_related('settings'),
        write_only=True)

    ssh_public_key = serializers.HyperlinkedRelatedField(
        view_name='sshpublickey-detail',
        lookup_field='uuid',
        queryset=core_models.SshPublicKey.objects.all(),
        required=False,
        write_only=True)

    external_ips = serializers.ListField(
        child=core_serializers.IPAddressField(),
        allow_null=True,
        required=False,
        validators=[IpCountValidator(1)])

    class Meta(structure_serializers.BaseResourceSerializer.Meta):
        model = models.Instance
        view_name = 'openstack-instance-detail'
        read_only_fields = ('start_time', 'cores', 'ram')
        fields = structure_serializers.BaseResourceSerializer.Meta.fields + (
            'cores', 'ram', 'external_ips',
            'flavor', 'image', 'ssh_public_key',
            'system_volume_size', 'data_volume_size',
            'user_data',
        )

    def get_fields(self):
        user = self.context['user']
        fields = super(InstanceSerializer, self).get_fields()
        fields['ssh_public_key'].queryset = fields['ssh_public_key'].queryset.filter(user=user)
        return fields

    def to_internal_value(self, data):
        if 'external_ips' in data and not data['external_ips']:
            data['external_ips'] = []
        internal_value = super(InstanceSerializer, self).to_internal_value(data)
        if 'external_ips' in internal_value:
            if not internal_value['external_ips']:
                internal_value['external_ips'] = None
            else:
                internal_value['external_ips'] = internal_value['external_ips'][0]

        return internal_value

    def validate(self, attrs):
        settings = attrs['service_project_link'].service.settings
        flavor = attrs['flavor']
        image = attrs['image']

        if any([flavor.settings != settings, image.settings != settings]):
            raise serializers.ValidationError(
                "Flavor and image must belong to the same service settings as service project link.")

        if attrs.get('system_volume_size', 0):
            attrs['system_volume_size'] = flavor.disk

        max_min_disk = (
            models.Image.objects.filter(settings=settings).aggregate(Max('min_disk'))
        )['min_disk__max']

        if max_min_disk > attrs['system_volume_size']:
            raise serializers.ValidationError(
                {'system_volume_size': "System volume size has to be greater than %s" % max_min_disk})

        return attrs
