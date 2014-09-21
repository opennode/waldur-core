from rest_framework import permissions as rf_permissions

from nodeconductor.core import viewsets
from nodeconductor.cloud import models
from nodeconductor.cloud import serializers
from nodeconductor.structure import filters


class FlavorViewSet(viewsets.ReadOnlyModelViewSet):
    model = models.Flavor
    serializer_class = serializers.FlavorSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter,)


class CloudViewSet(viewsets.ModelViewSet):
    model = models.Cloud
    serializer_class = serializers.CloudSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter,)
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)

