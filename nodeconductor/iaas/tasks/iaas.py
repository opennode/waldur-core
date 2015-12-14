# coding: utf-8
from __future__ import absolute_import, unicode_literals

import logging

from celery import shared_task

from nodeconductor.core.models import SynchronizationStates
from nodeconductor.core.tasks import tracked_processing, set_state, StateChangeError
from nodeconductor.iaas.log import event_logger
from nodeconductor.iaas import models
from nodeconductor.iaas.backend import CloudBackendError
from nodeconductor.monitoring import utils as monitoring_utils

logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.iaas.stop')
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

        monitoring_utils.delete_host_and_service(instance)
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
        monitoring_utils.create_host_and_service(imported_instance)
    else:
        # in case Instance object hasn't been created, emit an event for a user
        event_logger.instance_import.info(
            'Import of a virtual machine with backend id {instance_id} has failed.',
            event_type='iaas_instance_import_failed',
            event_context={'instance_id': instance_id})


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

    try:
        backend.push_membership_quotas(membership, quotas)
    except CloudBackendError:
        event_logger.membership.warning(
            'Failed to push quotas to cloud membership {cloud_name}.',
            event_type='iaas_membership_sync_failed',
            event_context={'membership': membership}
        )

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
    try:
        backend.pull_security_groups(membership)
    except CloudBackendError:
        event_logger.membership.warning(
            'Failed to pull security groups from cloud membership {cloud_name}.',
            event_type='iaas_membership_sync_failed',
            event_context={'membership': membership}
        )

    try:
        backend.pull_instances(membership)
    except CloudBackendError:
        event_logger.membership.warning(
            'Failed to pull instances from cloud membership {cloud_name}.',
            event_type='iaas_membership_sync_failed',
            event_context={'membership': membership}
        )

    try:
        backend.pull_resource_quota(membership)
        backend.pull_resource_quota_usage(membership)
    except CloudBackendError:
        event_logger.membership.warning(
            'Failed to pull resource quotas from cloud membership {cloud_name}.',
            event_type='iaas_membership_sync_failed',
            event_context={'membership': membership}
        )

    try:
        backend.pull_floating_ips(membership)
    except CloudBackendError:
        event_logger.membership.warning(
            'Failed to pull floating IPs from cloud membership {cloud_name}.',
            event_type='iaas_membership_sync_failed',
            event_context={'membership': membership}
        )

    # XXX not the best idea to register in the function
    sync_cloud_project_membership_with_zabbix.delay(membership.pk)


@shared_task
def pull_cloud_memberships():
    # TODO: Extract to a service
    queryset = models.CloudProjectMembership.objects.filter(state=SynchronizationStates.IN_SYNC)

    for membership in queryset.iterator():
        membership.schedule_syncing()
        membership.save()

        pull_cloud_membership.delay(membership.pk)


# TODO: split this task to smaller and group them in chain
@shared_task
@tracked_processing(
    models.CloudProjectMembership,
    processing_state='begin_syncing',
    desired_state='set_in_sync',
)
def sync_cloud_membership(membership_pk, is_membership_creation=False):
    membership = models.CloudProjectMembership.objects.get(pk=membership_pk)

    backend = membership.cloud.get_backend()

    # Propagate cloud-project membership itself
    try:
        backend.push_membership(membership)
    except CloudBackendError:
        event_logger.membership.warning(
            'Failed to create cloud membership {cloud_name}.',
            event_type='iaas_membership_sync_failed',
            event_context={'membership': membership}
        )

    # Propagate membership security groups
    try:
        backend.push_security_groups(membership, is_membership_creation=is_membership_creation)
    except CloudBackendError:
        logger.warn(
            'Failed to push security groups to cloud membership %s',
            membership.pk,
            exc_info=1,
        )
        event_logger.membership.warning(
            'Failed to push security groups to cloud membership {cloud_name}.',
            event_type='iaas_membership_sync_failed',
            event_context={'membership': membership}
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

    sync_cloud_project_membership_with_zabbix.delay(membership.pk)


@shared_task
def sync_cloud_project_membership_with_zabbix(membership_pk):
    membership = models.CloudProjectMembership.objects.get(pk=membership_pk)
    if not membership.tenant_id:
        logger.warn(
            'Cannot create zabbix host for membership %s - it does not have tenant_id',
            membership.pk,
            exc_info=1
        )
    else:
        logger.debug('Synchronizing cloud project membership %s with zabbix', membership.pk, exc_info=1)
        monitoring_utils.create_host(membership, warn_if_exists=False)


@shared_task
def check_cloud_memberships_quotas():
    # XXX: this task is replaced by quotas.handlers.check_quota_threshold_breach for openstack app
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
                event_logger.membership_quota.warning(
                    '{quota_name} quota threshold has been reached for project {project_name}.',
                    event_type='quota_threshold_reached',
                    event_context={
                        'quota': quota,
                        'cloud': membership.cloud,
                        'project': membership.project,
                        'project_group': membership.project.project_groups.first(),
                        'threshold': threshold * quota.limit,
                    })


@shared_task
def sync_instances_with_zabbix():
    instances = models.Instance.objects.exclude(backend_id='').values_list('uuid', flat=True)
    for instance_uuid in instances:
        sync_instance_with_zabbix.delay(instance_uuid)


@shared_task
def sync_instance_with_zabbix(instance_uuid):
    instance = models.Instance.objects.get(uuid=instance_uuid)
    logger.debug('Synchronizing instance %s with zabbix', instance.uuid, exc_info=1)
    monitoring_utils.create_host_and_service(instance, warn_if_exists=False)


@shared_task
def create_external_network(membership_pk, network_data):
    membership = models.CloudProjectMembership.objects.get(pk=membership_pk)
    backend = membership.cloud.get_backend()

    try:
        session = backend.create_session(keystone_url=membership.cloud.auth_url)
        neutron = backend.create_neutron_client(session)

        backend.get_or_create_external_network(membership, neutron, **network_data)
    except CloudBackendError:
        logger.warning('Failed to create external network for cloud project membership with id %s.', membership_pk)


@shared_task
def delete_external_network(membership_pk):
    membership = models.CloudProjectMembership.objects.get(pk=membership_pk)
    backend = membership.cloud.get_backend()

    try:
        session = backend.create_session(keystone_url=membership.cloud.auth_url)
        neutron = backend.create_neutron_client(session)

        backend.delete_external_network(membership, neutron)
    except CloudBackendError:
        logger.info('Failed to delete external network for cloud project membership with id %s.', membership_pk)


@shared_task
def detect_external_network(membership_pk):
    membership = models.CloudProjectMembership.objects.get(pk=membership_pk)
    backend = membership.cloud.get_backend()

    try:
        session = backend.create_session(keystone_url=membership.cloud.auth_url)
        neutron = backend.create_neutron_client(session)

        backend.detect_external_network(membership, neutron)
    except CloudBackendError:
        logger.warning('Failed to detect external network for cloud project membership with id %s.', membership_pk)


@shared_task
def allocate_floating_ip(membership_pk):
    membership = models.CloudProjectMembership.objects.get(pk=membership_pk)
    backend = membership.cloud.get_backend()

    try:
        session = backend.create_session(keystone_url=membership.cloud.auth_url)
        neutron = backend.create_neutron_client(session)

        backend.allocate_floating_ip_address(neutron, membership)
    except CloudBackendError:
        logger.warning('Failed to allocate floating IP for cloud project membership with id %s.', membership_pk)


@shared_task
def assign_floating_ip(floating_ip_uuid, instance_uuid):
    instance = models.Instance.objects.get(uuid=instance_uuid)
    backend = instance.cloud_project_membership.cloud.get_backend()

    floating_ip = models.FloatingIP.objects.get(uuid=floating_ip_uuid)

    try:
        session = backend.create_session(keystone_url=instance.cloud_project_membership.cloud.auth_url)
        nova = backend.create_nova_client(session)

        backend.assign_floating_ip_to_instance(nova, instance, floating_ip)
    except CloudBackendError:
        logger.warning('Failed to assign floating IP to the instance with id %s.', instance_uuid)


@shared_task
def update_cloud_project_membership_tenant_name(membership_pk):
    membership = models.CloudProjectMembership.objects.get(pk=membership_pk)
    backend = membership.cloud.get_backend()

    try:
        session = backend.create_session(keystone_url=membership.cloud.auth_url)
        keystone = backend.create_keystone_client(session)

        backend.update_tenant_name(membership, keystone)
    except CloudBackendError:
        logger.warning('Failed to update tenant name for cloud project membership with id %s.', membership_pk)
