import django_filters

from rest_framework import viewsets

from nodeconductor.core import filters as core_filters
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


class FlavorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Flavor.objects.all()
    serializer_class = serializers.FlavorSerializer
    lookup_field = 'uuid'


class ImageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Image.objects.all()
    serializer_class = serializers.ImageSerializer
    lookup_field = 'uuid'


class InstanceFilter(django_filters.FilterSet):
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

    name = django_filters.CharFilter(lookup_type='icontains')
    description = django_filters.CharFilter(lookup_type='icontains')
    state = django_filters.NumberFilter()

    # In order to return results when an invalid value is specified
    strict = False

    class Meta(object):
        model = models.Instance
        fields = [
            'name',
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
        ]
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
