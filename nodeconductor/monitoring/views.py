from rest_framework import permissions as rf_permissions
from rest_framework import viewsets

from nodeconductor.core.filters import DjangoMappingFilterBackend
from nodeconductor.monitoring.models import ResourceSlaStateTransition

from . import serializers, filters


class ResourceStateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ResourceSlaStateTransition.objects.all()
    serializer_class = serializers.ResourceStateSerializer
    permission_classes = (rf_permissions.IsAuthenticated,)
    filter_backends = (DjangoMappingFilterBackend, filters.ResourceScopeFilterBackend)
    filter_class = filters.ResourceStateFilter
