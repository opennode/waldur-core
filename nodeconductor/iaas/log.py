from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from nodeconductor.logging.log import EventLogger, event_logger
from nodeconductor.logging.views import ExternalAlertFilterBackend, BaseExternalFilter
from nodeconductor.structure import models as structure_models


class InstanceEventLogger(EventLogger):
    instance = 'structure.Resource'

    class Meta:
        event_types = (
            'iaas_instance_start_scheduled',
            'iaas_instance_start_succeeded',
            'iaas_instance_start_failed',

            'iaas_instance_stop_scheduled',
            'iaas_instance_stop_failed',
            'iaas_instance_stop_succeeded',

            'iaas_instance_restart_scheduled',
            'iaas_instance_restart_succeeded',
            'iaas_instance_restart_failed',

            'iaas_instance_creation_scheduled',
            'iaas_instance_creation_succeeded',
            'iaas_instance_creation_failed',
            'iaas_instance_update_succeeded',

            'iaas_instance_deletion_scheduled',
            'iaas_instance_deletion_succeeded',
            'iaas_instance_deletion_failed',

            'iaas_instance_application_failed',
            'iaas_instance_application_deployment_succeeded',
            'iaas_instance_application_became_available',
        )


class InstanceLicensesEventLogger(EventLogger):
    instance = 'iaas.Instance'
    licenses_types = list
    licenses_services_types = list

    class Meta:
        event_types = (
            'iaas_instance_licenses_added',
        )


class InstanceVolumeChangeEventLogger(EventLogger):
    instance = 'iaas.Instance'
    volume_size = int

    class Meta:
        event_types = (
            'iaas_instance_volume_extension_scheduled',
            'iaas_instance_volume_extension_succeeded',
            'iaas_instance_volume_extension_failed',
        )


class InstanceFlavorChangeEventLogger(EventLogger):
    instance = 'iaas.Instance'
    flavor = 'iaas.Flavor'

    class Meta:
        event_types = (
            'iaas_instance_flavor_change_scheduled',
            'iaas_instance_flavor_change_succeeded',
            'iaas_instance_flavor_change_failed',
        )


class InstanceImportEventLogger(EventLogger):
    instance_id = basestring

    class Meta:
        event_types = (
            'iaas_instance_import_scheduled',
            'iaas_instance_import_succeeded',
            'iaas_instance_import_failed',
        )


class MembershipEventLogger(EventLogger):
    membership = 'structure.ServiceProjectLink'

    class Meta:
        event_types = (
            'iaas_membership_sync_failed',
        )


class CloudEventLogger(EventLogger):
    cloud = 'iaas.Cloud'

    class Meta:
        event_types = (
            'iaas_service_sync_failed',
        )


class QuotaEventLogger(EventLogger):
    quota = 'quotas.Quota'
    cloud = 'iaas.Cloud'
    project = 'structure.Project'
    project_group = 'structure.ProjectGroup'
    threshold = float

    class Meta:
        event_types = (
            'quota_threshold_reached',
        )


event_logger.register('instance', InstanceEventLogger)
event_logger.register('instance_import', InstanceImportEventLogger)
event_logger.register('instance_volume', InstanceVolumeChangeEventLogger)
event_logger.register('instance_flavor', InstanceFlavorChangeEventLogger)
event_logger.register('instance_licenses', InstanceLicensesEventLogger)
event_logger.register('cloud', CloudEventLogger)
event_logger.register('membership', MembershipEventLogger)
event_logger.register('quota', QuotaEventLogger)


# XXX: This filter should be moved to structure application and support alerts filtering for all customer-related
# resources - not only OpenStack instances and memberships. (this should be done in issue NC-640)
class AggregateAlertFilter(BaseExternalFilter):
    """
    Filter alerts by instances/projects/memberships
    """

    def filter(self, request, queryset, view):
        from nodeconductor.iaas import serializers as iaas_serializers, models as iaas_models

        aggregate_serializer = iaas_serializers.StatsAggregateSerializer(data=request.query_params)
        aggregate_serializer.is_valid(raise_exception=True)

        projects_ids = aggregate_serializer.get_projects(request.user).values_list('id', flat=True)
        instances_ids = aggregate_serializer.get_instances(request.user).values_list('id', flat=True)
        memebersips_ids = aggregate_serializer.get_memberships(request.user).values_list('id', flat=True)

        aggregate_query = Q(
            content_type=ContentType.objects.get_for_model(structure_models.Project),
            object_id__in=projects_ids
        )
        aggregate_query |= Q(
            content_type=ContentType.objects.get_for_model(iaas_models.Instance),
            object_id__in=instances_ids
        )
        aggregate_query |= Q(
            content_type=ContentType.objects.get_for_model(iaas_models.CloudProjectMembership),
            object_id__in=memebersips_ids
        )
        queryset = queryset.filter(aggregate_query)
        return queryset

ExternalAlertFilterBackend.register(AggregateAlertFilter())
