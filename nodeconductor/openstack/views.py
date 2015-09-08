from django.conf import settings
from rest_framework import viewsets, decorators, exceptions, response, permissions, status
from rest_framework import filters as rf_filters

from nodeconductor.core import mixins as core_mixins
from nodeconductor.core import filters as core_filters
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.core.tasks import send_task
from nodeconductor.structure import views as structure_views
from nodeconductor.structure import filters as structure_filters
from nodeconductor.openstack import models, filters, serializers


class OpenStackServiceViewSet(structure_views.BaseServiceViewSet):
    queryset = models.OpenStackService.objects.all()
    serializer_class = serializers.ServiceSerializer
    import_serializer_class = serializers.InstanceImportSerializer


class OpenStackServiceProjectLinkFilter(structure_views.BaseServiceProjectLinkFilter):
    service = core_filters.URLFilter(viewset=OpenStackServiceViewSet, name='service__uuid')


class OpenStackServiceProjectLinkViewSet(structure_views.BaseServiceProjectLinkViewSet):
    queryset = models.OpenStackServiceProjectLink.objects.all()
    serializer_class = serializers.ServiceProjectLinkSerializer
    filter_class = OpenStackServiceProjectLinkFilter

    @decorators.detail_route(methods=['post'])
    def set_quotas(self, request, **kwargs):
        if not request.user.is_staff:
            raise exceptions.PermissionDenied()

        spl = self.get_object()
        if spl.state != SynchronizationStates.IN_SYNC:
            return response.Response(
                {'detail': 'Service project link must be in sync state for setting quotas'},
                status=status.HTTP_409_CONFLICT)

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
            {'status': 'Quota update was scheduled'}, status=status.HTTP_202_ACCEPTED)


class FlavorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Flavor.objects.all()
    serializer_class = serializers.FlavorSerializer
    lookup_field = 'uuid'


class ImageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Image.objects.all()
    serializer_class = serializers.ImageSerializer
    lookup_field = 'uuid'


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
            ssh_key=serializer.validated_data.get('ssh_public_key'))


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
            {'status': 'Deletion was scheduled'}, status=status.HTTP_202_ACCEPTED)
