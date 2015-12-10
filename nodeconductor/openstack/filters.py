import django_filters

from nodeconductor.core import filters as core_filters
from nodeconductor.structure import filters as structure_filters
from nodeconductor.structure.managers import filter_queryset_for_user
from nodeconductor.openstack import models


class OpenStackServiceProjectLinkFilter(structure_filters.BaseServiceProjectLinkFilter):
    service = core_filters.URLFilter(view_name='openstack-detail', name='service__uuid')


class InstanceFilter(structure_filters.BaseResourceFilter):

    class Meta(object):
        model = models.Instance
        fields = structure_filters.BaseResourceFilter.Meta.fields
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


class SecurityGroupFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(
        name='name',
        lookup_type='icontains',
    )
    description = django_filters.CharFilter(
        name='description',
        lookup_type='icontains',
    )
    service = django_filters.CharFilter(
        name='service_project_link__service__uuid',
    )
    project = django_filters.CharFilter(
        name='service_project_link__project__uuid',
    )
    settings_uuid = django_filters.CharFilter(
        name='service_project_link__service__settings__uuid'
    )
    service_project_link = core_filters.URLFilter(
        view_name='openstack-spl-detail',
        name='service_project_link__pk',
        lookup_field='pk',
    )
    state = core_filters.SynchronizationStateFilter()

    class Meta(object):
        model = models.SecurityGroup
        fields = [
            'name',
            'description',
            'service',
            'project',
            'service_project_link',
            'state',
        ]


class FloatingIPFilter(django_filters.FilterSet):
    project = django_filters.CharFilter(
        name='service_project_link__project__uuid',
    )
    service = django_filters.CharFilter(
        name='service_project_link__service__uuid',
    )

    class Meta(object):
        model = models.FloatingIP
        fields = [
            'project',
            'service',
            'status',
        ]


class FlavorFilter(structure_filters.ServicePropertySettingsFilter):

    class Meta(structure_filters.ServicePropertySettingsFilter.Meta):
        model = models.Flavor
        fields = dict({
            'cores': ['exact', 'gte', 'lte'],
            'ram': ['exact', 'gte', 'lte'],
            'disk': ['exact', 'gte', 'lte'],
        }, **{field: ['exact'] for field in structure_filters.ServicePropertySettingsFilter.Meta.fields})
        order_by = [
            'cores',
            '-cores',
            'ram',
            '-ram',
            'disk',
            '-disk',
        ]


class BackupScheduleFilter(django_filters.FilterSet):
    description = django_filters.CharFilter(
        lookup_type='icontains',
    )

    class Meta(object):
        model = models.BackupSchedule
        fields = (
            'description',
        )


class BackupFilter(django_filters.FilterSet):
    description = django_filters.CharFilter(
        lookup_type='icontains',
    )
    project = django_filters.CharFilter(
        name='instance__service_project_link__project__uuid',
    )

    class Meta(object):
        model = models.Backup
        fields = (
            'description',
            'project',
        )
