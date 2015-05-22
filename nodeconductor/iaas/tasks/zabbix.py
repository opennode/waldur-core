# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

from celery import shared_task
from django.conf import settings

from nodeconductor.iaas.models import Instance
from nodeconductor.iaas.tasks import iaas
from nodeconductor.monitoring.zabbix.api_client import ZabbixApiClient
from nodeconductor.monitoring.zabbix.errors import ZabbixError


logger = logging.getLogger(__name__)


@shared_task
def zabbix_create_host_and_service(instance_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    iaas.create_zabbix_host_and_service(instance)


@shared_task
def zabbix_update_host_visible_name(instance_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    try:
        zabbix_client = ZabbixApiClient()
        zabbix_client.update_host_visible_name(instance)
    except ZabbixError as e:
        # task does not have to fail if something is wrong with zabbix
        logger.error('Zabbix host visible name update has failed %s' % e, exc_info=1)


def _get_installation_state(instance):
    zabbix_settings = getattr(settings, 'NODECONDUCTOR', {}).get('MONITORING', {}).get('APPLICATION_ZABBIX', {})
    zabbix_client = ZabbixApiClient(settings=zabbix_settings)
    return zabbix_client.get_service_installation_state(instance)


@shared_task
def pull_instance_installation_state(instance_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    instance.installation_state = _get_installation_state(instance)
    instance.save()


@shared_task
def poll_instance_installation_state(instance_uuid, polling_time=0):
    poll_interval = 3
    max_polling_time = 20
    polling_time += poll_interval

    instance = Instance.objects.get(uuid=instance_uuid)
    instance.installation_state = _get_installation_state(instance)
    instance.save()
    if instance.installation_state != 'synced' and polling_time < max_polling_time:
        poll_instance_installation_state.apply_async(args=(instance_uuid, polling_time), countdown=poll_interval)
