from __future__ import unicode_literals

from rest_framework import permissions
from rest_framework import mixins
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from nodeconductor.cloud.models import Cloud
from nodeconductor.core import mixins as core_mixins
from nodeconductor.core import models as core_models
from nodeconductor.core import viewsets as core_viewsets
from nodeconductor.iaas import models
from nodeconductor.iaas import serializers
from nodeconductor.structure import filters
from nodeconductor.structure.filters import filter_queryset_for_user


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

        return super(InstanceViewSet, self).get_serializer_class()

    @action()
    def stop(self, request, uuid=None):
        # TODO: schedule stopping of a instance
        return Response({'status': 'Stopping was scheduled'})



class TemplateViewSet(core_viewsets.ReadOnlyModelViewSet):
    queryset = models.Template.objects.all()
    serializer_class = serializers.TemplateSerializer
    lookup_field = 'uuid'

    def get_queryset(self):
        queryset = super(TemplateViewSet, self).get_queryset()

        user = self.request.user

        if not user.is_staff:
            queryset = queryset.exclude(is_active=False)

        if self.request.method == 'GET':
            cloud_uuid = self.request.QUERY_PARAMS.get('cloud')
            if cloud_uuid is not None:
                cloud_queryset = filter_queryset_for_user(
                    Cloud.objects.all(), user)

                try:
                    cloud = cloud_queryset.get(uuid=cloud_uuid)
                except Cloud.DoesNotExist:
                    return queryset.none()

                queryset = queryset.filter(images__cloud=cloud)

        return queryset


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
