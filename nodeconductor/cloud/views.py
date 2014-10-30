from __future__ import unicode_literals

import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from keystoneclient.v2_0 import client as keystone_client
from keystoneclient.exceptions import CertificateConfigError, CMSError, ClientException

from rest_framework import exceptions
from rest_framework import mixins as rf_mixins
from rest_framework import permissions as rf_permissions
from rest_framework import viewsets as rf_viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from nodeconductor.cloud import models, serializers, tasks
from nodeconductor.core import viewsets, mixins
from nodeconductor.core.exceptions import ServiceUnavailableError
from nodeconductor.structure import filters as structure_filters
from nodeconductor.structure import models as structure_models


logger = logging.getLogger(__name__)


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

    def pre_save(self, cloud):
        super(CloudViewSet, self).pre_save(cloud)
        self._check_permission(cloud)

        # Generate cloud uuid in advance
        import uuid
        cloud.uuid = uuid.uuid4()

        # Here comes backend specific part, move to corresponding backend
        # Create user in keystone and populate username, password fields
        cloud.username = '{0}-{1}'.format(cloud.uuid.hex, cloud.name)

        from django.contrib.auth import get_user_model
        cloud.password = get_user_model().objects.make_random_password()

        nc_settings = getattr(settings, 'NODE_CONDUCTOR', {})
        openstacks = nc_settings.get('OPENSTACK_CREDENTIALS', ())

        try:
            openstack = next(o for o in openstacks if o['keystone_url'] == cloud.auth_url)

            keystone = keystone_client.Client(
                username=openstack['username'],
                password=openstack['password'],
                tenant_name=openstack['tenant'],
                auth_url=openstack['keystone_url'],
            )

            logging.info('Creating keystone user %s', cloud.username)
            keystone.users.create(
                name=cloud.username,
                password=cloud.password,
            )
            logging.info('Successfully created keystone user %s', cloud.username)
        except (ClientException, CertificateConfigError, CMSError, StopIteration):
            logger.exception('Failed to create keystone user %s', cloud.username)
            raise ServiceUnavailableError(detail='Error talking to OpenStack backend')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return serializers.CloudCreateSerializer

        return super(CloudViewSet, self).get_serializer_class()

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


class SecurityGroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.SecurityGroup.objects.all()
    serializer_class = serializers.SecurityGroupSerializer
    lookup_field = 'uuid'
