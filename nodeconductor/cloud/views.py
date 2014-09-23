from rest_framework import permissions as rf_permissions
from rest_framework import exceptions

from nodeconductor.core import viewsets
from nodeconductor.cloud import models
from nodeconductor.cloud import serializers
from nodeconductor.structure import filters as structure_filters
from nodeconductor.structure import models as structure_models


class FlavorViewSet(viewsets.ReadOnlyModelViewSet):
    model = models.Flavor
    serializer_class = serializers.FlavorSerializer
    lookup_field = 'uuid'
    filter_backends = (structure_filters.GenericRoleFilter,)


class CloudViewSet(viewsets.ModelViewSet):
    model = models.Cloud
    serializer_class = serializers.CloudSerializer
    lookup_field = 'uuid'
    filter_backends = (structure_filters.GenericRoleFilter,)
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)

    def pre_save(self, cloud):
        super(CloudViewSet, self).pre_save(cloud)

        if not cloud.customer.roles.filter(
                permission_group__user=self.request.user,
                role_type=structure_models.CustomerRole.OWNER,
        ).exists():
            raise exceptions.PermissionDenied()
