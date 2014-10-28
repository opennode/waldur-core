from django.shortcuts import get_object_or_404

from rest_framework import exceptions
from rest_framework import mixins as rf_mixins
from rest_framework import permissions as rf_permissions
from rest_framework import viewsets as rf_viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from nodeconductor.cloud import models, serializers, tasks
from nodeconductor.core import viewsets, mixins
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

    Cloud represents an instance of an account in a certain service accessible over APIs, for example OpenStack IaaS instance.

    Clouds are connected to customers, whereas the cloud may belong to one customer only, and the customer may have multiple clouds.

    Clouds are connected to projects, whereas the cloud may belong to multiple projects, and the project may contain multiple clouds.

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

    def _check_permission(self, cloud):
        """
        Raises PermissionDenied exception if user does not have permission to cloud
        """
        if not self.request.user.is_staff and not cloud.customer.roles.filter(
                permission_group__user=self.request.user,
                role_type=structure_models.CustomerRole.OWNER,
        ).exists():
            raise exceptions.PermissionDenied()

    def get_serializer_class(self):
        return serializers.CloudSerializer

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        context = super(CloudViewSet, self).get_serializer_context()
        context['user'] = self.request.user
        return context

    def pre_save(self, cloud):
        super(CloudViewSet, self).pre_save(cloud)
        self._check_permission(cloud)

    @action()
    def sync(self, request, uuid):
        """
        Starts cloud synchronization
        """
        cloud = get_object_or_404(models.Cloud, uuid=uuid)
        self._check_permission(cloud)
        cloud.sync()
        return Response({'status': "Cloud synchronization was scheduled"}, status=200)


class CloudProjectMembershipViewSet(rf_mixins.CreateModelMixin,
                                    rf_mixins.RetrieveModelMixin,
                                    rf_mixins.DestroyModelMixin,
                                    mixins.ListModelMixin,
                                    rf_viewsets.GenericViewSet):
    """
    List of project-cloud connections

    Staff and customer owners can add/delete new connections

    Managers and administrators can view connections
    """
    queryset = models.CloudProjectMembership.objects.all()
    serializer_class = serializers.CloudProjectMembershipSerializer
    filter_backends = (structure_filters.GenericRoleFilter,)
    permission_classes = (rf_permissions.IsAuthenticated, rf_permissions.DjangoObjectPermissions)

    def post_save(self, membership, created):
        if created:
            tasks.create_backend_membership.delay(membership)


class SecurityGroupsViewSet(rf_viewsets.GenericViewSet):

    def list(self, request, *args, **kwargs):
        return Response(models.SecurityGroups.groups, status=200)
