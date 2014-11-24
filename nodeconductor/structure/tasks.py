from __future__ import unicode_literals

import logging

from celery import shared_task

from nodeconductor.monitoring.zabbix.api_client import ZabbixApiClient


logger = logging.getLogger(__name__)


@shared_task
def create_zabbix_hostgroup(project):
    zabbix_client = ZabbixApiClient()
    zabbix_client.create_hostgroup(project)


@shared_task
def delete_zabbix_hostgroup(project):
    zabbix_client = ZabbixApiClient()
    zabbix_client.delete_hostgroup(project)
