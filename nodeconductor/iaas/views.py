from rest_framework import filters
from rest_framework import mixins
from rest_framework import viewsets

from nodeconductor.core import models as core_models
from nodeconductor.core import permissions
from nodeconductor.iaas import models
from nodeconductor.iaas import serializers


class InstanceViewSet(mixins.CreateModelMixin,
                      mixins.RetrieveModelMixin,
                      mixins.ListModelMixin,
                      viewsets.GenericViewSet):
    queryset = models.Instance.objects.all()
    serializer_class = serializers.InstanceSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.DjangoObjectPermissionsFilter,)
    permission_classes = (permissions.DjangoObjectLevelPermissions,)

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


class PurchaseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Purchase.objects.all()
    serializer_class = serializers.PurchaseSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.DjangoObjectPermissionsFilter,)
    permission_classes = (permissions.DjangoObjectLevelPermissions,)