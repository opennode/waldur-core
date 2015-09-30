from __future__ import unicode_literals

from rest_framework import viewsets

from nodeconductor.structure import filters as structure_filters
from nodeconductor.structure import views as structure_views
from nodeconductor.oracle import models
from nodeconductor.oracle import serializers


class OracleServiceViewSet(structure_views.BaseServiceViewSet):
    queryset = models.OracleService.objects.all()
    serializer_class = serializers.ServiceSerializer


class OracleServiceProjectLinkViewSet(structure_views.BaseServiceProjectLinkViewSet):
    queryset = models.OracleServiceProjectLink.objects.all()
    serializer_class = serializers.ServiceProjectLinkSerializer


class ZoneViewSet(structure_views.BaseServicePropertyViewSet):
    queryset = models.Zone.objects.all()
    serializer_class = serializers.ZoneSerializer
    lookup_field = 'uuid'
    filter_class = structure_filters.ServicePropertySettingsFilter


class TemplateViewSet(structure_views.BaseServicePropertyViewSet):
    queryset = models.Template.objects.all()
    serializer_class = serializers.TemplateSerializer
    lookup_field = 'uuid'
    filter_class = structure_filters.ServicePropertySettingsFilter


class DatabaseViewSet(structure_views.BaseResourceViewSet):
    queryset = models.Database.objects.all()
    serializer_class = serializers.DatabaseSerializer

    def perform_provision(self, serializer):
        resource = serializer.save()
        backend = resource.get_backend()
        backend.provision(
            resource,
            zone=serializer.validated_data['zone'],
            template=serializer.validated_data['template'],
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password'])
