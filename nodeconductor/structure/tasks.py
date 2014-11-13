from __future__ import unicode_literals

import logging

from django.conf import settings
from celery import shared_task

from nodeconductor.core import zabbix


logger = logging.getLogger(__name__)


@shared_task
def create_zabbix_hostgroup(project):
    z = zabbix.Zabbix(settings.ZABBIX['IAAS'])
    z.create_hostgroup(project)


@shared_task
def delete_zabbix_hostgroup(project):
    z = zabbix.Zabbix(settings.ZABBIX['IAAS'])
    z.delete_hostgroup(project)
