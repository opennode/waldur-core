from __future__ import unicode_literals

from rest_framework import serializers

from nodeconductor.structure import serializers as structure_serializers
from nodeconductor.oracle import models


class ServiceSerializer(structure_serializers.BaseServiceSerializer):

    class Meta(structure_serializers.BaseServiceSerializer.Meta):
        model = models.OracleService
        view_name = 'oracle-detail'


class ZoneSerializer(structure_serializers.BasePropertySerializer):

    class Meta(object):
        model = models.Zone
        view_name = 'oracle-zone-detail'
        fields = ('url', 'uuid', 'name')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


class TemplateSerializer(structure_serializers.BasePropertySerializer):

    type = serializers.ReadOnlyField(source='get_type_display')

    class Meta(object):
        model = models.Template
        view_name = 'oracle-template-detail'
        fields = ('url', 'uuid', 'name', 'type')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


class ServiceProjectLinkSerializer(structure_serializers.BaseServiceProjectLinkSerializer):

    class Meta(structure_serializers.BaseServiceProjectLinkSerializer.Meta):
        model = models.OracleServiceProjectLink
        view_name = 'oracle-spl-detail'
        extra_kwargs = {
            'service': {'lookup_field': 'uuid', 'view_name': 'oracle-detail'},
        }


class DatabaseSerializer(structure_serializers.BaseResourceSerializer):

    service = serializers.HyperlinkedRelatedField(
        source='service_project_link.service',
        view_name='oracle-detail',
        read_only=True,
        lookup_field='uuid')

    service_project_link = serializers.HyperlinkedRelatedField(
        view_name='oracle-spl-detail',
        queryset=models.OracleServiceProjectLink.objects.all(),
        write_only=True)

    zone = serializers.HyperlinkedRelatedField(
        view_name='oracle-zone-detail',
        lookup_field='uuid',
        queryset=models.Zone.objects.all().select_related('settings'),
        write_only=True)

    template = serializers.HyperlinkedRelatedField(
        view_name='oracle-template-detail',
        lookup_field='uuid',
        queryset=models.Template.objects.filter(
            type=models.Template.Types.DB).select_related('settings'),
        write_only=True)

    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta(structure_serializers.BaseResourceSerializer.Meta):
        model = models.Database
        view_name = 'oracle-database-detail'
        fields = structure_serializers.BaseResourceSerializer.Meta.fields + (
            'backend_database_sid', 'backend_service_name',
            'zone', 'template', 'username', 'password'
        )

    def validate(self, attrs):
        settings = attrs['service_project_link'].service.settings
        zone = attrs['zone']
        template = attrs['zone']

        if any([zone.settings != settings, template.settings != settings]):
            raise serializers.ValidationError(
                "Zone and template must belong to the same service settings.")

        return attrs
