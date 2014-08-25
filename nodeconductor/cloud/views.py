from rest_framework import viewsets

from nodeconductor.cloud import models
from nodeconductor.cloud import serializers
from nodeconductor.structure import filters


class FlavorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Flavor.objects.all()
    serializer_class = serializers.FlavorSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.CustomerOrProjectRoleFilter,)

    customer_path = 'cloud__projects__customer'
    project_path = 'cloud__projects'


class CloudViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Cloud.objects.all()
    serializer_class = serializers.CloudSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.ProjectRoleFilter,)

    project_path = 'projects'
