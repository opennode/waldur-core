import django_filters

from django.conf import settings
from rest_framework import viewsets, decorators, exceptions, response, status

from nodeconductor.core import filters as core_filters
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.core.tasks import send_task
from nodeconductor.structure import views as structure_views
from nodeconductor.openstack import models, serializers


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
            {'status': 'Quota update was scheduled'},
            status=status.HTTP_202_ACCEPTED)


class FlavorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Flavor.objects.all()
    serializer_class = serializers.FlavorSerializer
    lookup_field = 'uuid'


class ImageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Image.objects.all()
    serializer_class = serializers.ImageSerializer
    lookup_field = 'uuid'


class InstanceFilter(structure_views.BaseResourceFilter):
    project = django_filters.CharFilter(
        name='service_project_link__project__uuid',
        lookup_type='icontains',
        distinct=True)

    project_name = django_filters.CharFilter(
        name='service_project_link__project__name',
        lookup_type='icontains',
        distinct=True)

    project_group_name = django_filters.CharFilter(
        name='service_project_link__project__project_groups__name',
        lookup_type='icontains',
        distinct=True)

    project_group = django_filters.CharFilter(
        name='service_project_link__project__project_groups__uuid',
        distinct=True)

    customer = django_filters.CharFilter(
        name='service_project_link__project__customer__uuid',
        distinct=True)

    customer_name = django_filters.CharFilter(
        name='service_project_link__project__customer__name',
        lookup_type='icontains',
        distinct=True)

    customer_native_name = django_filters.CharFilter(
        name='service_project_link__project__customer__native_name',
        lookup_type='icontains',
        distinct=True)

    customer_abbreviation = django_filters.CharFilter(
        name='service_project_link__project__customer__abbreviation',
        lookup_type='icontains',
        distinct=True)

    description = django_filters.CharFilter(lookup_type='icontains')
    state = django_filters.NumberFilter()

    # In order to return results when an invalid value is specified
    strict = False

    class Meta(object):
        model = models.Instance
        fields = structure_views.BaseResourceFilter.Meta.fields + (
            'description',
            'customer',
            'customer_name',
            'customer_native_name',
            'customer_abbreviation',
            'project',
            'project_name',
            'project_group_name',
            'project_group',
            'state',
            'start_time',
            'created',
            'ram',
            'cores',
            'system_volume_size',
            'data_volume_size',
        )
        order_by = [
            'name',
            '-name',
            'state',
            '-state',
            'service_project_link__project__customer__name',
            '-service_project_link__project__customer__name',
            'service_project_link__project__customer__native_name',
            '-service_project_link__project__customer__native_name',
            'service_project_link__project__customer__abbreviation',
            '-service_project_link__project__customer__abbreviation',
            'service_project_link__project__name',
            '-service_project_link__project__name',
            'service_project_link__project__project_groups__name',
            '-service_project_link__project__project_groups__name',
            'created',
            '-created',
            'ram',
            '-ram',
            'cores',
            '-cores',
            'system_volume_size',
            '-system_volume_size',
            'data_volume_size',
            '-data_volume_size',
        ]
        order_by_mapping = {
            # Proper field naming
            'customer_name': 'service_project_link__project__customer__name',
            'customer_native_name': 'service_project_link__project__customer__native_name',
            'customer_abbreviation': 'service_project_link__project__customer__abbreviation',
            'project_name': 'service_project_link__project__name',
            'project_group_name': 'service_project_link__project__project_groups__name',

            # Backwards compatibility
            'project__customer__name': 'service_project_link__project__customer__name',
            'project__name': 'service_project_link__project__name',
            'project__project_groups__name': 'service_project_link__project__project_groups__name',
        }


class InstanceViewSet(structure_views.BaseResourceViewSet):
    queryset = models.Instance.objects.all()
    serializer_class = serializers.InstanceSerializer
    filter_class = InstanceFilter

    def perform_provision(self, serializer):
        resource = serializer.save()
        backend = resource.get_backend()
        backend.provision(
            resource,
            flavor=serializer.validated_data['flavor'],
            image=serializer.validated_data['image'],
            ssh_key=serializer.validated_data.get('ssh_public_key'))
