from __future__ import unicode_literals

import logging

from django.conf import settings
from celery import shared_task

from nodeconductor.core import zabbix


logger = logging.getLogger(__name__)


@shared_task
def create_zabbix_hostgroup(project):
    zabbix_client = zabbix.Zabbix(settings.ZABBIX['IAAS'])
    zabbix_client.create_hostgroup(project)


@shared_task
def delete_zabbix_hostgroup(project):
    zabbix_client = zabbix.Zabbix(settings.ZABBIX['IAAS'])
    zabbix_client.delete_hostgroup(project)
