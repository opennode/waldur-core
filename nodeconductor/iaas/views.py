from rest_framework import mixins
from rest_framework import viewsets

from nodeconductor.iaas import models
from nodeconductor.iaas import serializers
from nodeconductor.core import models as core_models


class InstanceViewSet(mixins.CreateModelMixin,
                      mixins.RetrieveModelMixin,
                      mixins.ListModelMixin,
                      viewsets.GenericViewSet):
    queryset = models.Instance.objects.all()
    serializer_class = serializers.InstanceSerializer
    lookup_field = 'uuid'

    def get_queryset(self):
        queryset = super(InstanceViewSet, self).get_queryset()
        queryset = queryset.filter(flavor__cloud__organisation__users=self.request.user)
        return queryset

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return serializers.InstanceCreateSerializer

        return super(InstanceViewSet, self).get_serializer_class()


class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Template.objects.all()
    serializer_class = serializers.TemplateSerializer
    lookup_field = 'uuid'


class SshKeyViewSet(viewsets.ModelViewSet):
    queryset = core_models.SshPublicKey.objects.all()
    serializer_class = serializers.SshKeySerializer
    lookup_field = 'uuid'

    def pre_save(self, key):
        key.user = self.request.user
