from __future__ import unicode_literals

from rest_framework import (
    viewsets, decorators, permissions,
    filters, mixins, response, status)

from nodeconductor.core import mixins as core_mixins
from nodeconductor.structure import filters as structure_filters
from nodeconductor.oracle import models
from nodeconductor.oracle import serializers


class ServiceViewSet(core_mixins.UserContextMixin, viewsets.ModelViewSet):
    queryset = models.OracleService.objects.all()
    serializer_class = serializers.ServiceSerializer
    lookup_field = 'uuid'
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)
    filter_backends = (structure_filters.GenericRoleFilter, filters.DjangoFilterBackend)


class ServiceProjectLinkViewSet(mixins.CreateModelMixin,
                                mixins.RetrieveModelMixin,
                                mixins.DestroyModelMixin,
                                mixins.ListModelMixin,
                                viewsets.GenericViewSet):

    queryset = models.OracleServiceProjectLink.objects.all()
    serializer_class = serializers.ServiceProjectLinkSerializer
    filter_backends = (structure_filters.GenericRoleFilter, filters.DjangoFilterBackend)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)


class ZoneViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Zone.objects.all()
    serializer_class = serializers.ZoneSerializer
    lookup_field = 'uuid'


class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Template.objects.all()
    serializer_class = serializers.TemplateSerializer
    lookup_field = 'uuid'
