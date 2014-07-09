from rest_framework import viewsets

from nodeconductor.iaas import models
from nodeconductor.iaas import serializers


class InstanceViewSet(viewsets.ModelViewSet):
    queryset = models.Instance.objects.all()
    serializer_class = serializers.InstanceSerializer
    lookup_field = 'uuid'

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return serializers.InstanceCreateSerializer

        return super(InstanceViewSet, self).get_serializer_class()


class FlavorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Flavor.objects.all()
    serializer_class = serializers.FlavorSerializer
    lookup_field = 'uuid'


class CloudViewSet(viewsets.ModelViewSet):
    queryset = models.Cloud.objects.all()
    serializer_class = serializers.CloudSerializer
    lookup_field = 'uuid'


class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Template.objects.all()
    serializer_class = serializers.TemplateSerializer
    lookup_field = 'uuid'
