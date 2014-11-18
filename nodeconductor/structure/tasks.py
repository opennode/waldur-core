from __future__ import unicode_literals

import logging

from django.conf import settings
from celery import shared_task

from nodeconductor.monitoring.zabbix.api_client import ZabbixApiClient


logger = logging.getLogger(__name__)


@shared_task
def create_zabbix_hostgroup(project):
    zabbix_client = ZabbixApiClient(settings.NODECONDUCTOR['ZABBIX'])
    zabbix_client.create_hostgroup(project)


@shared_task
def delete_zabbix_hostgroup(project):
    zabbix_client = ZabbixApiClient(settings.NODECONDUCTOR['ZABBIX'])
    zabbix_client.delete_hostgroup(project)
