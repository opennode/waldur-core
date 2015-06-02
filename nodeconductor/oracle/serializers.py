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
            'project': {'lookup_field': 'uuid'},
        }
