from nodeconductor.structure import views as structure_views

from . import models, serializers


class TestServiceViewSet(structure_views.BaseServiceViewSet):
    queryset = models.TestService.objects.all()
    serializer_class = serializers.ServiceSerializer


class TestServiceProjectLinkViewSet(structure_views.BaseServiceProjectLinkViewSet):
    queryset = models.TestServiceProjectLink.objects.all()
    serializer_class = serializers.ServiceProjectLinkSerializer


class TestNewInstanceViewSet(structure_views.ResourceViewSet):
    queryset = models.TestNewInstance.objects.all()
    serializer_class = serializers.NewInstanceSerializer
