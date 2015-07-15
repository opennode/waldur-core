from rest_framework import viewsets

from nodeconductor.structure import views as structure_views
from nodeconductor.openstack import models, serializers


class OpenStackServiceViewSet(structure_views.BaseServiceViewSet):
    queryset = models.Service.objects.all()
    serializer_class = serializers.ServiceSerializer


class OpenStackServiceProjectLinkViewSet(structure_views.BaseServiceProjectLinkViewSet):
    queryset = models.ServiceProjectLink.objects.all()
    serializer_class = serializers.ServiceProjectLinkSerializer


class FlavorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Flavor.objects.all()
    serializer_class = serializers.FlavorSerializer
    lookup_field = 'uuid'


class ImageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Image.objects.all()
    serializer_class = serializers.ImageSerializer
    lookup_field = 'uuid'
