# coding: utf-8
from __future__ import absolute_import, unicode_literals

import logging

from celery import shared_task

from nodeconductor.core import models as core_models
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.core.tasks import tracked_processing
from nodeconductor.core.log import EventLoggerAdapter
from nodeconductor.iaas import models
from nodeconductor.iaas.backend import CloudBackendError
from nodeconductor.monitoring.zabbix.api_client import ZabbixApiClient
from nodeconductor.monitoring.zabbix.errors import ZabbixError

logger = logging.getLogger(__name__)
event_log = EventLoggerAdapter(logger)


# XXX: There are no usages of this error.
class ResizingError(KeyError, models.Instance.DoesNotExist):
    pass


def create_zabbix_host_and_service(instance):
    try:
        zabbix_client = ZabbixApiClient()
        zabbix_client.create_host(instance)
        zabbix_client.create_service(instance)
    except ZabbixError as e:
        # task does not have to fail if something is wrong with zabbix
        logger.error('Zabbix host creation flow has broken %s' % e, exc_info=1)


def delete_zabbix_host_and_service(instance):
    try:
        zabbix_client = ZabbixApiClient()
        zabbix_client.delete_host(instance)
        zabbix_client.delete_service(instance)
    except ZabbixError as e:
        # task does not have to fail if something is wrong with zabbix
        logger.error('Zabbix host deletion flow has broken %s' % e, exc_info=1)


@shared_task
@tracked_processing(models.Instance, processing_state='begin_provisioning', desired_state='set_online')
def schedule_provisioning(instance_uuid):
    instance = models.Instance.objects.get(uuid=instance_uuid)

    backend = instance.flavor.cloud.get_backend()
    backend.provision_instance(instance)
    create_zabbix_host_and_service(instance)


@shared_task
@tracked_processing(models.Instance, processing_state='begin_stopping', desired_state='set_offline')
def schedule_stopping(instance_uuid):
    instance = models.Instance.objects.get(uuid=instance_uuid)

    backend = instance.flavor.cloud.get_backend()
    backend.stop_instance(instance)


@shared_task
@tracked_processing(models.Instance, processing_state='begin_starting', desired_state='set_online')
def schedule_starting(instance_uuid):
    instance = models.Instance.objects.get(uuid=instance_uuid)

    backend = instance.flavor.cloud.get_backend()
    backend.start_instance(instance)


@shared_task
@tracked_processing(models.Instance, processing_state='begin_deleting', desired_state='set_deleted')
def schedule_deleting(instance_uuid):
    instance = models.Instance.objects.get(uuid=instance_uuid)

    backend = instance.flavor.cloud.get_backend()
    backend.delete_instance(instance)

    delete_zabbix_host_and_service(instance)


@shared_task
@tracked_processing(models.Instance, processing_state='begin_resizing', desired_state='set_offline')
def update_flavor(instance_uuid):
    instance = models.Instance.objects.get(uuid=instance_uuid)

    backend = instance.flavor.cloud.get_backend()
    backend.update_flavor(instance)


@shared_task
@tracked_processing(models.Instance, processing_state='begin_resizing', desired_state='set_offline')
def extend_disk(instance_uuid):
    instance = models.Instance.objects.get(uuid=instance_uuid)

    backend = instance.flavor.cloud.get_backend()
    backend.extend_disk(instance)


@shared_task
def push_instance_security_groups(instance_uuid):
    instance = models.Instance.objects.get(uuid=instance_uuid)

    backend = instance.flavor.cloud.get_backend()
    backend.push_instance_security_groups(instance)


@shared_task
@tracked_processing(
    models.Cloud,
    processing_state='begin_syncing',
    desired_state='set_in_sync',
)
def pull_cloud_account(cloud_account_uuid):
    cloud_account = models.Cloud.objects.get(uuid=cloud_account_uuid)

    backend = cloud_account.get_backend()
    backend.pull_cloud_account(cloud_account)


@shared_task
def pull_cloud_accounts():
    # TODO: Extract to a service
    queryset = models.Cloud.objects.filter(state=SynchronizationStates.IN_SYNC)

    for cloud_account in queryset.iterator():
        cloud_account.schedule_syncing()
        cloud_account.save()

        pull_cloud_account.delay(cloud_account.uuid.hex)


@shared_task
@tracked_processing(
    models.Cloud,
    processing_state='begin_syncing',
    desired_state='set_in_sync',
)
def sync_cloud_account(cloud_account_uuid):
    cloud = models.Cloud.objects.get(uuid=cloud_account_uuid)

    backend = cloud.get_backend()
    backend.push_cloud_account(cloud)
    backend.pull_cloud_account(cloud)


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

    # Propagate membership security groups
    try:
        backend.push_security_groups(membership)
    except CloudBackendError:
        logger.warn(
            'Failed to push security groups to cloud membership %s',
            membership.pk,
            exc_info=1,
        )


@shared_task
@tracked_processing(
    models.Cloud,
    processing_state='begin_syncing',
    desired_state='set_in_sync',
)
def pull_images(cloud_account_uuid):
    cloud = models.Cloud.objects.get(uuid=cloud_account_uuid)
    cloud.get_backend().pull_images(cloud)


@shared_task
def push_ssh_public_keys(ssh_public_keys_uuids, membership_pks):
    public_keys = models.SshPublicKey.objects.filter(uuid__in=ssh_public_keys_uuids)

    existing_keys = set(k.uuid.hex for k in public_keys)
    missing_keys = set(ssh_public_keys_uuids) - existing_keys
    if missing_keys:
        logging.warn(
            'Failed to push missing public keys: %s',
            ', '.join(missing_keys)
        )

    membership_queryset = models.CloudProjectMembership.objects.filter(
        pk__in=membership_pks)

    for membership in membership_queryset.iterator():
        if membership.state != core_models.SynchronizationStates.IN_SYNC:
            logging.warn(
                'Not pushing public keys to cloud membership %s which is in state %s',
                membership.pk, membership.get_state_display()
            )
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
