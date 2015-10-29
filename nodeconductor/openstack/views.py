from django.conf import settings
from rest_framework import viewsets, decorators, exceptions, response, permissions, status
from rest_framework import filters as rf_filters

from nodeconductor.core import mixins as core_mixins
from nodeconductor.core.exceptions import IncorrectStateException
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.core.tasks import send_task
from nodeconductor.structure import views as structure_views
from nodeconductor.structure import filters as structure_filters
from nodeconductor.openstack import models, filters, serializers


class OpenStackServiceViewSet(structure_views.BaseServiceViewSet):
    queryset = models.OpenStackService.objects.all()
    serializer_class = serializers.ServiceSerializer
    import_serializer_class = serializers.InstanceImportSerializer


class OpenStackServiceProjectLinkViewSet(structure_views.BaseServiceProjectLinkViewSet):
    queryset = models.OpenStackServiceProjectLink.objects.all()
    serializer_class = serializers.ServiceProjectLinkSerializer
    filter_class = filters.OpenStackServiceProjectLinkFilter

    @decorators.detail_route(methods=['post'])
    def set_quotas(self, request, **kwargs):
        if not request.user.is_staff:
            raise exceptions.PermissionDenied()

        spl = self.get_object()
        if spl.state != SynchronizationStates.IN_SYNC:
            return IncorrectStateException(
                "Service project link must be in stable state.")

        serializer = serializers.ServiceProjectLinkQuotaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = dict(serializer.validated_data)
        if data.get('instances') is not None:
            quotas = settings.NODECONDUCTOR.get('OPENSTACK_QUOTAS_INSTANCE_RATIOS', {})
            volume_ratio = quotas.get('volumes', 4)
            snapshots_ratio = quotas.get('snapshots', 20)

            data['volumes'] = volume_ratio * data['instances']
            data['snapshots'] = snapshots_ratio * data['instances']

        send_task('structure', 'sync_service_project_links')(spl.to_string(), quotas=data)

        return response.Response(
            {'detail': 'Quota update was scheduled'}, status=status.HTTP_202_ACCEPTED)

    @decorators.detail_route(methods=['post', 'delete'])
    def external_network(self, request, pk=None):
        spl = self.get_object()
        if request.method == 'DELETE':
            if spl.external_network_id:
                send_task('openstack', 'sync_external_network')(spl.to_string(), 'delete')
                return response.Response(
                    {'detail': 'External network deletion has been scheduled.'},
                    status=status.HTTP_202_ACCEPTED)
            else:
                return response.Response(
                    {'detail': 'External network does not exist.'},
                    status=status.HTTP_204_NO_CONTENT)

        serializer = serializers.ExternalNetworkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        send_task('openstack', 'sync_external_network')(spl.to_string(), 'create', serializer.data)

        return response.Response(
            {'detail': 'External network creation has been scheduled.'},
            status=status.HTTP_202_ACCEPTED)

    @decorators.detail_route(methods=['post'])
    def allocate_floating_ip(self, request, pk=None):
        spl = self.get_object()
        if not spl.external_network_id:
            return response.Response(
                {'detail': 'Service project link should have an external network ID.'},
                status=status.HTTP_409_CONFLICT)

        elif spl.state not in SynchronizationStates.STABLE_STATES:
            raise IncorrectStateException(
                "Service project link must be in stable state.")

        send_task('openstack', 'allocate_floating_ip')(spl.to_string())

        return response.Response(
            {'detail': 'Floating IP allocation has been scheduled.'},
            status=status.HTTP_202_ACCEPTED)


class FlavorViewSet(structure_views.BaseServicePropertyViewSet):
    queryset = models.Flavor.objects.all()
    serializer_class = serializers.FlavorSerializer
    lookup_field = 'uuid'
    filter_class = filters.FlavorFilter


class ImageViewSet(structure_views.BaseServicePropertyViewSet):
    queryset = models.Image.objects.all()
    serializer_class = serializers.ImageSerializer
    lookup_field = 'uuid'
    filter_class = structure_filters.ServicePropertySettingsFilter


class InstanceViewSet(structure_views.BaseResourceViewSet):
    queryset = models.Instance.objects.all()
    serializer_class = serializers.InstanceSerializer
    filter_class = filters.InstanceFilter

    def perform_update(self, serializer):
        super(InstanceViewSet, self).perform_update(serializer)
        send_task('openstack', 'sync_instance_security_groups')(self.get_object().uuid.hex)

    def perform_provision(self, serializer):
        resource = serializer.save()
        backend = resource.get_backend()
        backend.provision(
            resource,
            flavor=serializer.validated_data['flavor'],
            image=serializer.validated_data['image'],
            ssh_key=serializer.validated_data.get('ssh_public_key'),
            skip_external_ip_assignment=serializer.validated_data['skip_external_ip_assignment'])

    @decorators.detail_route(methods=['post'])
    def assign_floating_ip(self, request, uuid):
        instance = self.get_object()

        serializer = serializers.AssignFloatingIpSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        if not instance.service_project_link.external_network_id:
            return response.Response(
                {'detail': 'External network ID of the service project link is missing.'},
                status=status.HTTP_409_CONFLICT)
        elif instance.service_project_link.state not in SynchronizationStates.STABLE_STATES:
            raise IncorrectStateException(
                "Service project link of instance should be in stable state.")
        elif instance.state not in instance.States.STABLE_STATES:
            raise IncorrectStateException(
                "Cannot add floating IP to instance in unstable state.")

        send_task('openstack', 'assign_floating_ip')(
            instance.uuid.hex, serializer.validated_data['floating_ip_uuid'])

        return response.Response(
            {'detail': 'Assigning floating IP to the instance has been scheduled.'},
            status=status.HTTP_202_ACCEPTED)


class SecurityGroupViewSet(core_mixins.UpdateOnlyStableMixin, viewsets.ModelViewSet):
    queryset = models.SecurityGroup.objects.all()
    serializer_class = serializers.SecurityGroupSerializer
    lookup_field = 'uuid'
    filter_class = filters.SecurityGroupFilter
    filter_backends = (structure_filters.GenericRoleFilter, rf_filters.DjangoFilterBackend)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)

    def perform_create(self, serializer):
        security_group = serializer.save()
        send_task('openstack', 'sync_security_group')(security_group.uuid.hex, 'create')

    def perform_update(self, serializer):
        super(SecurityGroupViewSet, self).perform_update(serializer)
        security_group = self.get_object()
        security_group.schedule_syncing()
        security_group.save()
        send_task('openstack', 'sync_security_group')(security_group.uuid.hex, 'update')

    def destroy(self, request, *args, **kwargs):
        security_group = self.get_object()
        security_group.schedule_syncing()
        security_group.save()
        send_task('openstack', 'sync_security_group')(security_group.uuid.hex, 'delete')
        return response.Response(
            {'detail': 'Deletion was scheduled'}, status=status.HTTP_202_ACCEPTED)


class FloatingIPViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.FloatingIP.objects.all()
    serializer_class = serializers.FloatingIPSerializer
    lookup_field = 'uuid'
    filter_class = filters.FloatingIPFilter
    filter_backends = (structure_filters.GenericRoleFilter, rf_filters.DjangoFilterBackend)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoObjectPermissions)
