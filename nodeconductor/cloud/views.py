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
    """List of VM instance flavors that are accessible by this user.

    VM instance flavor is a pre-defined set of virtual hardware parameters that the instance will use: CPU, memory, disk size etc.

    VM instance flavor is not to be confused with VM template -- flavor is a set of virtual hardware parameters whereas template is a definition of a system to be installed on this instance.

    Flavors are connected to clouds, whereas the flavor may belong to one cloud only, and the cloud may have multiple flavors.

    Staff members can list all available flavors for any cloud and create new flavors.

    Customer owners can list all flavors for all the clouds that belong to any of the customers they own.

    Project administrators can list all the flavors for all the clouds that are connected to any of the projects they are administrators in.

    Project managers can list all the flavors for all the clouds that are connected to any of the projects they are managers in.
    """

    queryset = models.Flavor.objects.all()
    serializer_class = serializers.FlavorSerializer
    lookup_field = 'uuid'
    filter_backends = (structure_filters.GenericRoleFilter,)


class CloudViewSet(viewsets.ModelViewSet):
    """List of clouds that are accessible by this user.

    TODO: Cloud definition.

    Clouds are connected to projects, whereas the cloud may belong to multiple projects, and the project may contain multiple clouds.

    Clouds are also connected to customers, whereas the cloud may belong to one customer only, and the customer may have multiple clouds.

    Staff members can list all available clouds for any project and/or customer and create new clouds.

    Customer owners can list all clouds that belong to any of the customers they own. Customer owners can also create clouds for the customers they own.

    Project administrators can list all the clouds that are connected to any of the projects they are administrators in.

    Project managers can list all the clouds that are connected to any of the projects they are managers in.
    """

    queryset = models.Cloud.objects.all().prefetch_related('flavors')
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
