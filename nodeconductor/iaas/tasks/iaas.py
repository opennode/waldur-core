# coding: utf-8
from __future__ import absolute_import, unicode_literals

import logging

from celery import shared_task

from nodeconductor.core import models as core_models
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.core.tasks import tracked_processing, set_state, StateChangeError
from nodeconductor.core.log import EventLoggerAdapter
from nodeconductor.iaas import models
from nodeconductor.iaas.backend import CloudBackendError
from nodeconductor.monitoring.zabbix.api_client import ZabbixApiClient
from nodeconductor.monitoring.zabbix.errors import ZabbixError

logger = logging.getLogger(__name__)
event_logger = EventLoggerAdapter(logger)


# XXX: There are no usages of this error.
class ResizingError(KeyError, models.Instance.DoesNotExist):
    pass


def create_zabbix_host_and_service(instance, warn_if_exists=True):
    try:
        zabbix_client = ZabbixApiClient()
        zabbix_client.create_host(instance, warn_if_host_exists=warn_if_exists)
        zabbix_client.create_service(instance, warn_if_service_exists=warn_if_exists)
    except Exception as e:
        # task does not have to fail if something is wrong with zabbix
        logger.error('Zabbix host creation flow has broken %s' % e, exc_info=1)
        event_logger.error(
            'Zabbix host creation flow has broken %s', e,
            extra={'instance': instance, 'event_type': 'zabbix_host_creation'}
        )


def delete_zabbix_host_and_service(instance):
    try:
        zabbix_client = ZabbixApiClient()
        zabbix_client.delete_host(instance)
        zabbix_client.delete_service(instance)
    except ZabbixError as e:
        # task does not have to fail if something is wrong with zabbix
        logger.error('Zabbix host deletion flow has broken %s' % e, exc_info=1)
        event_logger.error(
            'Zabbix host deletion flow has broken %s', e,
            extra={'instance': instance, 'event_type': 'zabbix_host_deletion'}
        )


@shared_task
@tracked_processing(models.Instance, processing_state='begin_provisioning', desired_state='set_online')
def schedule_provisioning(instance_uuid, backend_flavor_id, system_volume_id=None, data_volume_id=None):
    instance = models.Instance.objects.get(uuid=instance_uuid)

    backend = instance.cloud_project_membership.cloud.get_backend()
    try:
        backend.provision_instance(instance, backend_flavor_id, system_volume_id, data_volume_id)
    finally:
        # the function below should never fail
        create_zabbix_host_and_service(instance)


@shared_task
@tracked_processing(models.Instance, processing_state='begin_stopping', desired_state='set_offline')
def schedule_stopping(instance_uuid):
    instance = models.Instance.objects.get(uuid=instance_uuid)

    backend = instance.cloud_project_membership.cloud.get_backend()
    backend.stop_instance(instance)


@shared_task
@tracked_processing(models.Instance, processing_state='begin_restarting', desired_state='set_restarted')
def schedule_restarting(instance_uuid):
    instance = models.Instance.objects.get(uuid=instance_uuid)

    backend = instance.cloud_project_membership.cloud.get_backend()
    backend.restart_instance(instance)


@shared_task
@tracked_processing(models.Instance, processing_state='begin_starting', desired_state='set_online')
def schedule_starting(instance_uuid):
    instance = models.Instance.objects.get(uuid=instance_uuid)

    backend = instance.cloud_project_membership.cloud.get_backend()
    backend.start_instance(instance)


@shared_task
def schedule_deleting(instance_uuid):
    try:
        set_state(models.Instance, instance_uuid, 'begin_deleting')
    except StateChangeError:
        # No logging is needed since set_state already logged everything
        return

    # noinspection PyBroadException
    try:
        instance = models.Instance.objects.get(uuid=instance_uuid)

        backend = instance.cloud_project_membership.cloud.get_backend()
        backend.delete_instance(instance)

        delete_zabbix_host_and_service(instance)
    except Exception:
        # noinspection PyProtectedMember
        logger.exception('Failed to begin deleting Instance with id %s', instance_uuid)
        set_state(models.Instance, instance_uuid, 'set_erred')
    else:
        # Actually remove the instance from the database
        models.Instance.objects.filter(uuid=instance_uuid).delete()


@shared_task
@tracked_processing(models.Instance, processing_state='begin_resizing', desired_state='set_offline')
def extend_disk(instance_uuid):
    instance = models.Instance.objects.get(uuid=instance_uuid)

    backend = instance.cloud_project_membership.cloud.get_backend()
    backend.extend_disk(instance)


@shared_task
def import_instance(membership_pk, instance_id, template_id=None):
    membership = models.CloudProjectMembership.objects.get(pk=membership_pk)

    backend = membership.cloud.get_backend()
    imported_instance = backend.import_instance(membership, instance_id, template_id)
    if imported_instance:
        create_zabbix_host_and_service(imported_instance)
    else:
        # in case Instance object hasn't been created, emit an event for a user
        event_logger.info('Import of a virtual machine with backend id %s has failed.', instance_id,
                          extra={'event_type': 'iaas_instance_import_failed'})


@shared_task
def push_instance_security_groups(instance_uuid):
    instance = models.Instance.objects.get(uuid=instance_uuid)

    backend = instance.cloud_project_membership.cloud.get_backend()
    backend.push_instance_security_groups(instance)


@shared_task
@tracked_processing(
    models.CloudProjectMembership,
    processing_state='begin_syncing',
    desired_state='set_in_sync',
)
def push_cloud_membership_quotas(membership_pk, quotas):
    membership = models.CloudProjectMembership.objects.get(pk=membership_pk)

    backend = membership.cloud.get_backend()
    backend.push_membership_quotas(membership, quotas)

    # Pull created membership quotas
    try:
        backend.pull_resource_quota(membership)
        backend.pull_resource_quota_usage(membership)
    except CloudBackendError:
        logger.warn(
            'Failed to pull resource quota and usage data to cloud membership %s',
            membership_pk,
            exc_info=1,
        )


@shared_task
def pull_service_statistics():
    # TODO: Extract to a service
    queryset = models.Cloud.objects.filter(state=SynchronizationStates.IN_SYNC)

    services = {}
    for cloud in queryset.iterator():
        services.setdefault(cloud.auth_url, [])
        services[cloud.auth_url].append(cloud)

    for auth_url in services:
        stats, backend = None, None
        for cloud in services[auth_url]:
            if not backend:
                backend = cloud.get_backend()
            if stats:
                backend.pull_service_statistics(cloud, service_stats=stats)
            else:
                stats = backend.pull_service_statistics(cloud)


@shared_task
@tracked_processing(
    models.CloudProjectMembership,
    processing_state='begin_syncing',
    desired_state='set_in_sync',
)
def pull_cloud_membership(membership_pk):
    membership = models.CloudProjectMembership.objects.get(pk=membership_pk)

    backend = membership.cloud.get_backend()
    backend.pull_security_groups(membership)
    backend.pull_instances(membership)
    backend.pull_resource_quota(membership)
    backend.pull_resource_quota_usage(membership)
    backend.pull_floating_ips(membership)


@shared_task
def pull_cloud_memberships():
    # TODO: Extract to a service
    queryset = models.CloudProjectMembership.objects.filter(state=SynchronizationStates.IN_SYNC)

    for membership in queryset.iterator():
        membership.schedule_syncing()
        membership.save()

        pull_cloud_membership.delay(membership.pk)


@shared_task
@tracked_processing(
    models.CloudProjectMembership,
    processing_state='begin_syncing',
    desired_state='set_in_sync',
)
def sync_cloud_membership(membership_pk):
    membership = models.CloudProjectMembership.objects.get(pk=membership_pk)

    backend = membership.cloud.get_backend()

    # Propagate cloud-project membership itself
    backend.push_membership(membership)

    # Propagate ssh public keys of users involved in the project
    for public_key in core_models.SshPublicKey.objects.filter(
            user__groups__projectrole__project=membership.project).iterator():
        try:
            backend.push_ssh_public_key(membership, public_key)
        except CloudBackendError:
            logger.warn(
                'Failed to push public key %s to cloud membership %s',
                public_key.uuid, membership.pk,
                exc_info=1,
            )
            event_logger.warning(
                'Failed to push public key %s to cloud membership %s.',
                public_key.uuid, membership.pk,
                extra={'project': membership.project, 'cloud': membership.cloud, 'event_type': 'sync_cloud_membership'}
            )

    # Propagate membership security groups
    try:
        backend.push_security_groups(membership)
    except CloudBackendError:
        logger.warn(
            'Failed to push security groups to cloud membership %s',
            membership.pk,
            exc_info=1,
        )
        event_logger.warning(
            'Failed to push security groups to cloud membership %s.',
            public_key.uuid, membership.pk,
            extra={'project': membership.project, 'cloud': membership.cloud, 'event_type': 'sync_cloud_membership'}
        )

    # Pull created membership quotas
    try:
        backend.pull_resource_quota(membership)
        backend.pull_resource_quota_usage(membership)
    except CloudBackendError:
        logger.warn(
            'Failed to pull resource quota and usage data to cloud membership %s',
            membership.pk,
            exc_info=1,
        )


@shared_task
def push_ssh_public_keys(ssh_public_keys_uuids, membership_pks):
    public_keys = core_models.SshPublicKey.objects.filter(uuid__in=ssh_public_keys_uuids)

    existing_keys = set(k.uuid.hex for k in public_keys)
    missing_keys = set(ssh_public_keys_uuids) - existing_keys
    if missing_keys:
        logging.warn(
            'Failed to push missing public keys: %s',
            ', '.join(missing_keys)
        )

    membership_queryset = models.CloudProjectMembership.objects.filter(
        pk__in=membership_pks)

    potential_rerunnable = []
    for membership in membership_queryset.iterator():
        if membership.state != core_models.SynchronizationStates.IN_SYNC:
            logging.warn(
                'Not pushing public keys to cloud membership %s which is in state %s.',
                membership.pk, membership.get_state_display()
            )
            if membership.state != core_models.SynchronizationStates.ERRED:
                # reschedule a task for this membership if membership is in a sane state
                logging.debug(
                    'Rescheduling synchronisation of keys for membership %s in state %s.',
                    membership.pk, membership.get_state_display()
                )
                potential_rerunnable.append(membership.id)
            continue

        backend = membership.cloud.get_backend()
        for public_key in public_keys:
            try:
                backend.push_ssh_public_key(membership, public_key)
            except CloudBackendError:
                logger.warn(
                    'Failed to push public key %s to cloud membership %s',
                    public_key.uuid, membership.pk,
                    exc_info=1,
                )
    # reschedule sync to membership that were blocked
    if potential_rerunnable:
        push_ssh_public_keys.delay(ssh_public_keys_uuids, potential_rerunnable)


@shared_task
def check_cloud_memberships_quotas():
    threshold = 0.80  # Could have been configurable...

    queryset = (
        models.CloudProjectMembership.objects
        .all()
        .select_related(
            'cloud',
            'cloud__customer',
            'project',
        )
        .prefetch_related(
            'project__project_groups',
        )
    )

    for membership in queryset.iterator():
        for quota in membership.quotas.all():
            if quota.is_exceeded(threshold=threshold):
                event_logger.warning(
                    '%s quota threshold has been reached for %s.', quota.name, membership.project.name,
                    extra=dict(
                        event_type='quota_threshold_reached',
                        quota_type=quota.name,
                        quota_container_type=membership,
                        cloud=membership.cloud,
                        project=membership.project,
                        project_group=membership.project.project_groups.first(),
                        threshold=threshold * quota.limit,
                        resource_usage=quota.usage,
                    ))


@shared_task
def sync_instances_with_zabbix():
    instances = models.Instance.objects.exclude(backend_id='').values_list('uuid', flat=True)
    for instance_uuid in instances:
        sync_instance_with_zabbix.delay(instance_uuid)


@shared_task
def sync_instance_with_zabbix(instance_uuid):
    instance = models.Instance.objects.get(uuid=instance_uuid)
    logger.info('Synchronizing instance %s with zabbix', instance.uuid, exc_info=1)
    create_zabbix_host_and_service(instance, warn_if_exists=False)
