from rest_framework import exceptions
from rest_framework import mixins as rf_mixins
from rest_framework import permissions as rf_permissions
from rest_framework import viewsets as rf_viewsets

from nodeconductor.cloud import models
from nodeconductor.cloud import serializers
from nodeconductor.core import viewsets, mixins
from nodeconductor.structure import filters
from nodeconductor.structure import filters as structure_filters
from nodeconductor.structure import models as structure_models


class FlavorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Flavor.objects.all()
    serializer_class = serializers.FlavorSerializer
    lookup_field = 'uuid'
    filter_backends = (structure_filters.GenericRoleFilter,)


class CloudViewSet(viewsets.ModelViewSet):
    queryset = models.Cloud.objects.all().prefetch_related('flavors')
    serializer_class = serializers.CloudSerializer
    lookup_field = 'uuid'
    filter_backends = (structure_filters.GenericRoleFilter,)
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)

    def pre_save(self, cloud):
        super(CloudViewSet, self).pre_save(cloud)

        if not self.request.user.is_staff and not cloud.customer.roles.filter(
                permission_group__user=self.request.user,
                role_type=structure_models.CustomerRole.OWNER,
        ).exists():
            raise exceptions.PermissionDenied()


class CloudProjectMembershipViewSet(rf_mixins.CreateModelMixin,
                                    rf_mixins.RetrieveModelMixin,
                                    rf_mixins.DestroyModelMixin,
                                    mixins.ListModelMixin,
                                    rf_viewsets.GenericViewSet):
    queryset = models.Cloud.projects.through.objects.all()
    serializer_class = serializers.CloudProjectMembershipSerializer
    filter_backends = (filters.GenericRoleFilter,)

# XXX: This should be put to models
filters.set_permissions_for_model(
    models.Cloud.projects.through,
    customer_path='cloud__customer',
)
