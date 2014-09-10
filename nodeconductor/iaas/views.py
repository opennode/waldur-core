from __future__ import unicode_literals

from rest_framework import permissions
from rest_framework import mixins
from rest_framework import viewsets

from nodeconductor.core import mixins as core_mixins
from nodeconductor.core import models as core_models
from nodeconductor.core import viewsets as core_viewsets
from nodeconductor.iaas import models
from nodeconductor.iaas import serializers
from nodeconductor.structure import filters
from nodeconductor.structure.models import ProjectRole


class InstanceViewSet(mixins.CreateModelMixin,
                      mixins.RetrieveModelMixin,
                      core_mixins.ListModelMixin,
                      core_mixins.UpdateOnlyModelMixin,
                      viewsets.GenericViewSet):
    model = models.Instance
    serializer_class = serializers.InstanceSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter,)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return serializers.InstanceCreateSerializer
        for instance in self.queryset:
            if models.Instance.objects.filter(project__roles__permission_group__user=self.request.user,
                                              project__roles__role_type=ProjectRole.ADMINISTRATOR,
                                              pk=instance.pk).exists():
                return serializers.InstanceAdminSerializer

        return super(InstanceViewSet, self).get_serializer_class()


class TemplateViewSet(core_viewsets.ReadOnlyModelViewSet):
    model = models.Template
    serializer_class = serializers.TemplateSerializer
    lookup_field = 'uuid'


class SshKeyViewSet(core_viewsets.ModelViewSet):
    model = core_models.SshPublicKey
    serializer_class = serializers.SshKeySerializer
    lookup_field = 'uuid'

    def pre_save(self, key):
        key.user = self.request.user


class PurchaseViewSet(core_viewsets.ReadOnlyModelViewSet):
    model = models.Purchase
    serializer_class = serializers.PurchaseSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter,)


class ImageViewSet(core_viewsets.ReadOnlyModelViewSet):
    model = models.Image
    serializer_class = serializers.ImageSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.GenericRoleFilter,)
