from __future__ import unicode_literals

from rest_framework import filters
from rest_framework import mixins
from rest_framework import viewsets

from nodeconductor.core import mixins as core_mixins
from nodeconductor.core import models as core_models
from nodeconductor.core import viewsets as core_viewsets
from nodeconductor.iaas import models
from nodeconductor.iaas import serializers
from nodeconductor.structure.models import ProjectRole


class InstanceViewSet(mixins.CreateModelMixin,
                      mixins.RetrieveModelMixin,
                      mixins.ListModelMixin,
                      core_mixins.UpdateOnlyModelMixin,
                      viewsets.GenericViewSet):
    queryset = models.Instance.objects.all()
    serializer_class = serializers.InstanceSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.DjangoObjectPermissionsFilter,)

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return serializers.InstanceCreateSerializer
        for instance in self.queryset:
            if models.Instance.objects.filter(project__roles__permission_group__user=self.request.user,
                                              project__roles__role_type=ProjectRole.ADMINISTRATOR,
                                              pk=instance.pk).exists():
                return serializers.InstanceAdminSerializer

        return super(InstanceViewSet, self).get_serializer_class()


class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Template.objects.all()
    serializer_class = serializers.TemplateSerializer
    lookup_field = 'uuid'


class SshKeyViewSet(core_viewsets.ModelViewSet):
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
