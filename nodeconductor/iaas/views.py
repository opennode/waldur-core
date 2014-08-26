from __future__ import unicode_literals

from rest_framework import mixins
from rest_framework import viewsets

from nodeconductor.core import mixins as core_mixins
from nodeconductor.core import models as core_models
from nodeconductor.core import viewsets as core_viewsets
from nodeconductor.iaas import models
from nodeconductor.iaas import serializers
from nodeconductor.structure import filters


class InstanceViewSet(mixins.CreateModelMixin,
                      mixins.RetrieveModelMixin,
                      mixins.ListModelMixin,
                      core_mixins.UpdateOnlyModelMixin,
                      viewsets.GenericViewSet):
    model = models.Instance
    serializer_class = serializers.InstanceSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter,)

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return serializers.InstanceCreateSerializer

        return super(InstanceViewSet, self).get_serializer_class()


class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    model = models.Template
    serializer_class = serializers.TemplateSerializer
    lookup_field = 'uuid'


class SshKeyViewSet(core_viewsets.ModelViewSet):
    model = core_models.SshPublicKey
    serializer_class = serializers.SshKeySerializer
    lookup_field = 'uuid'

    def pre_save(self, key):
        key.user = self.request.user


class PurchaseViewSet(viewsets.ReadOnlyModelViewSet):
    model = models.Purchase
    serializer_class = serializers.PurchaseSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter,)
