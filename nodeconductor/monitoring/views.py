from rest_framework import permissions as rf_permissions
from rest_framework import viewsets

from nodeconductor.core.filters import DjangoMappingFilterBackend

from . import serializers, filters, models


class ResourceSlaStateTransitionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.ResourceSlaStateTransition.objects.all().order_by('-timestamp')
    serializer_class = serializers.ResourceSlaStateTransitionSerializer
    permission_classes = (rf_permissions.IsAuthenticated,)
    filter_backends = (DjangoMappingFilterBackend, filters.ResourceScopeFilterBackend)
    filter_class = filters.ResourceStateFilter
