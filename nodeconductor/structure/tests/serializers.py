from rest_framework import serializers

from nodeconductor.structure import serializers as structure_serializers

from . import models


class ServiceSerializer(structure_serializers.BaseServiceSerializer):
    class Meta(structure_serializers.BaseServiceSerializer.Meta):
        model = models.TestService
        extra_kwargs = {
            'url': {'lookup_field': 'uuid', 'view_name': 'test-detail'},
            'customer': {'lookup_field': 'uuid'},
            'settings': {'lookup_field': 'uuid'},
        }


class ServiceProjectLinkSerializer(structure_serializers.BaseServiceProjectLinkSerializer):
    class Meta(structure_serializers.BaseServiceProjectLinkSerializer.Meta):
        model = models.TestServiceProjectLink
        extra_kwargs = {
            'url': {'view_name': 'test-spl-detail'},
            'service': {'lookup_field': 'uuid', 'view_name': 'oracle-detail'},
        }


class InstanceSerializer(structure_serializers.BaseResourceSerializer):

    service = serializers.HyperlinkedRelatedField(
        source='service_project_link.service',
        view_name='test-detail',
        read_only=True,
        lookup_field='uuid')

    service_project_link = serializers.HyperlinkedRelatedField(
        view_name='test-spl-detail',
        queryset=models.TestServiceProjectLink.objects.all())

    class Meta(structure_serializers.BaseResourceSerializer.Meta):
        model = models.TestInstance
        extra_kwargs = {
            'url': {'lookup_field': 'uuid', 'view_name': 'test-instances-detail'},
        }


class NewInstanceSerializer(structure_serializers.BaseResourceSerializer):

    service = serializers.HyperlinkedRelatedField(
        source='service_project_link.service',
        view_name='test-detail',
        read_only=True,
        lookup_field='uuid')

    service_project_link = serializers.HyperlinkedRelatedField(
        view_name='test-spl-detail',
        queryset=models.TestServiceProjectLink.objects.all())

    class Meta(structure_serializers.BaseResourceSerializer.Meta):
        model = models.TestNewInstance
        extra_kwargs = {
            'url': {'view_name': 'test-new-instances-detail'}
        }
