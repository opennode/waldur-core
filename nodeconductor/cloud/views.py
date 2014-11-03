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
    http://nodeconductor.readthedocs.org/en/latest/api/api.html#flavor-management
    """

    queryset = models.Flavor.objects.all()
    serializer_class = serializers.FlavorSerializer
    lookup_field = 'uuid'
    filter_backends = (structure_filters.GenericRoleFilter,)


class CloudViewSet(viewsets.ModelViewSet):
    """List of clouds that are accessible by this user.
    http://nodeconductor.readthedocs.org/en/latest/api/api.html#cloud-model
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
    http://nodeconductor.readthedocs.org/en/latest/api/api.html#link-cloud-to-a-project
    """
    queryset = models.CloudProjectMembership.objects.all()
    serializer_class = serializers.CloudProjectMembershipSerializer
    filter_backends = (structure_filters.GenericRoleFilter,)
    permission_classes = (rf_permissions.IsAuthenticated, rf_permissions.DjangoObjectPermissions)

    def post_save(self, membership, created):
        if created:
            tasks.create_backend_membership.delay(membership)


class SecurityGroupViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List of openstack security groups
    http://nodeconductor.readthedocs.org/en/latest/api/api.html#security-group-management
    """
    queryset = models.SecurityGroup.objects.all()
    serializer_class = serializers.SecurityGroupSerializer
    lookup_field = 'uuid'
