# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

from celery import shared_task

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
