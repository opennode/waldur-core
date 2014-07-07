from rest_framework import generics
from rest_framework import viewsets

from nodeconductor.vm import models
from nodeconductor.vm import serializers


class InstanceViewSet(viewsets.ModelViewSet):
    queryset = models.Instance.objects.all()
    serializer_class = serializers.InstanceSerializer

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return serializers.InstanceCreateSerializer

        return super(InstanceViewSet, self).get_serializer_class()


class FlavorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Flavor.objects.all()
    serializer_class = serializers.FlavorSerializer


class CloudViewSet(viewsets.ModelViewSet):
    queryset = models.Cloud.objects.all()
    serializer_class = serializers.CloudSerializer


class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Template.objects.all()
    serializer_class = serializers.TemplateSerializer
