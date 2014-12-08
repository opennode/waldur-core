# coding: utf-8
from __future__ import absolute_import, unicode_literals

import logging

from celery import shared_task

from nodeconductor.cloud import models as cloud_models
from nodeconductor.core.tasks import tracked_processing
from nodeconductor.core.log import EventLoggerAdapter
from nodeconductor.iaas import models
from nodeconductor.monitoring.zabbix.api_client import ZabbixApiClient
from nodeconductor.monitoring.zabbix.errors import ZabbixError

logger = logging.getLogger(__name__)
event_log = EventLoggerAdapter(logger)


class ResizingError(KeyError, models.Instance.DoesNotExist):
    pass


def create_zabbix_host_and_service(instance):
    try:
        zabbix_client = ZabbixApiClient()
        zabbix_client.create_host(instance)
        zabbix_client.create_service(instance)
    except ZabbixError as e:
        # task does not have to fail if something is wrong with zabbix
        logger.error('Zabbix host creation flow has broken', e, exc_info=1)


def delete_zabbix_host_and_service(instance):
    try:
        zabbix_client = ZabbixApiClient()
        zabbix_client.delete_host(instance)
        zabbix_client.delete_service(instance)
    except ZabbixError as e:
        # task does not have to fail if something is wrong with zabbix
        logger.error('Zabbix host deletion flow has broken', e, exc_info=1)


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
    cloud_models.Cloud,
    processing_state='begin_syncing',
    desired_state='set_in_sync',
)
def pull_cloud_account(cloud_account_uuid):
    cloud_account = cloud_models.Cloud.objects.get(uuid=cloud_account_uuid)

    backend = cloud_account.get_backend()
    backend.pull_cloud_account(cloud_account)


@shared_task
@tracked_processing(
    cloud_models.CloudProjectMembership,
    processing_state='begin_syncing',
    desired_state='set_in_sync',
)
def pull_cloud_membership(membership_pk):
    membership = cloud_models.CloudProjectMembership.objects.get(pk=membership_pk)

    backend = membership.cloud.get_backend()
    backend.pull_security_groups(membership)
    # TODO: pull_instances
