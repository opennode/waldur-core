from __future__ import unicode_literals

from rest_framework import serializers

from nodeconductor.structure import models as structure_models
from nodeconductor.structure import serializers as structure_serializers
from nodeconductor.oracle import models


class ZoneSerializer(serializers.HyperlinkedModelSerializer):

    class Meta(object):
        model = models.Zone
        view_name = 'oracle-zone-detail'
        fields = ('url', 'uuid', 'name')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


class TemplateSerializer(serializers.HyperlinkedModelSerializer):

    type = serializers.ReadOnlyField(source='get_type_display')

    class Meta(object):
        model = models.Template
        view_name = 'oracle-template-detail'
        fields = ('url', 'uuid', 'name', 'type')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


class ServiceSerializer(structure_serializers.BaseServiceSerializer):

    SERVICE_TYPE = structure_models.ServiceSettings.Types.Oracle

    class Meta(structure_serializers.BaseServiceSerializer.Meta):
        model = models.OracleService
        view_name = 'oracle-detail'


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

    class Meta(structure_serializers.BaseResourceSerializer.Meta):
        model = models.Database
        view_name = 'oracle-database-detail'


class DatabaseCreateSerializer(structure_serializers.PermissionFieldFilteringMixin,
                               serializers.HyperlinkedModelSerializer):

    service_project_link = serializers.HyperlinkedRelatedField(
        view_name='oracle-spl-detail',
        queryset=models.OracleServiceProjectLink.objects.filter(
            service__settings__type=structure_models.ServiceSettings.Types.Oracle),
        required=True,
        write_only=True)

    zone = serializers.HyperlinkedRelatedField(
        view_name='oracle-zone-detail',
        lookup_field='uuid',
        queryset=models.Zone.objects.all().select_related('settings'),
        required=True,
        write_only=True)

    template = serializers.HyperlinkedRelatedField(
        view_name='oracle-template-detail',
        lookup_field='uuid',
        queryset=models.Template.objects.filter(
            type=models.Template.Types.DB).select_related('settings'),
        required=True,
        write_only=True)

    username = serializers.CharField(required=True, write_only=True)
    database_sid = serializers.CharField(required=True, write_only=True)
    service_name = serializers.CharField(required=True, write_only=True)

    class Meta(object):
        model = models.Database
        fields = (
            'url', 'uuid',
            'name', 'description', 'service_project_link',
            'zone', 'template', 'username', 'database_sid', 'service_name',
        )

    def get_filtered_field_names(self):
        return 'service_project_link',

    def validate(self, attrs):
        settings = attrs['service_project_link'].service.settings
        zone = attrs['zone']
        template = attrs['zone']

        if any([zone.settings != settings, template.settings != settings]):
            raise serializers.ValidationError(
                "Zone and template must belong to the same service settings.")

        return attrs

    def create(self, validated_data):
        data = validated_data.copy()
        # Remove `virtual` properties which ain't actually belong to the model
        for prop in ('zone', 'template', 'username', 'database_sid', 'service_name'):
            if prop in data:
                del data[prop]

        return super(DatabaseCreateSerializer, self).create(data)
