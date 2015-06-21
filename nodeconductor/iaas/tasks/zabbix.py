# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

from celery import shared_task

from nodeconductor.core.tasks import retry_if_false
from nodeconductor.iaas.models import Instance
from nodeconductor.monitoring.zabbix.api_client import ZabbixApiClient
from nodeconductor.monitoring.zabbix.errors import ZabbixError
from nodeconductor.monitoring import utils as monitoring_utils


logger = logging.getLogger(__name__)


@shared_task
def zabbix_create_host_and_service(instance_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    monitoring_utils.create_host_and_service(instance)


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
    zabbix_client = ZabbixApiClient()
    return zabbix_client.get_application_installation_state(instance)


@shared_task
def pull_instance_installation_state(instance_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    installation_state = _get_installation_state(instance)
    if installation_state in ['NO DATA', 'NOT OK'] and instance.installation_state in ['FAIL', 'OK']:
        installation_state = 'FAIL'
    if instance.installation_state != installation_state:
        instance.installation_state = installation_state
        instance.save()


@shared_task
def pull_instances_installation_state():
    instances = Instance.objects.filter(
        installation_state__in=['OK', 'FAIL'],
        state__in=Instance.States.STABLE_STATES,
        type=Instance.Services.PAAS)
    for instance in instances:
        installation_state = _get_installation_state(instance)
        if installation_state != 'OK':
            installation_state = 'FAIL'
        if instance.installation_state != installation_state:
            instance.installation_state = installation_state
            instance.save()


@shared_task(max_retries=60, default_retry_delay=60)
@retry_if_false
def poll_instance_installation_state(instance_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    instance.installation_state = _get_installation_state(instance)
    instance.save()
    return instance.installation_state == 'OK'
