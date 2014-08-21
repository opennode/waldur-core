from rest_framework import filters
from rest_framework import viewsets

from nodeconductor.cloud import models
from nodeconductor.cloud import serializers


class FlavorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Flavor.objects.all()
    serializer_class = serializers.FlavorSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.DjangoObjectPermissionsFilter,)


class CloudViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Cloud.objects.all()
    serializer_class = serializers.CloudSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.DjangoObjectPermissionsFilter,)