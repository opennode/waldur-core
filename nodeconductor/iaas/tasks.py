# coding: utf-8
from __future__ import absolute_import, unicode_literals

import logging

from celery import shared_task
from django.db import transaction

from nodeconductor.core.tasks import tracked_processing, set_state
from nodeconductor.core.log import EventLoggerAdapter
from nodeconductor.cloud import models as cloud_models
from nodeconductor.iaas import models
from nodeconductor.monitoring.zabbix.api_client import ZabbixApiClient
from nodeconductor.monitoring.zabbix.errors import ZabbixError

from celery.utils import log

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
