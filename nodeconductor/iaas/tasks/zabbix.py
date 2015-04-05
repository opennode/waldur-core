# -*- coding: utf-8 -*-
from __future__ import absolute_import

from celery import shared_task

from nodeconductor.iaas.models import Instance
from nodeconductor.iaas.tasks import iaas


@shared_task
def zabbix_create_host_and_service(instance_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    iaas.create_zabbix_host_and_service(instance)


@shared_task
def zabbix_update_host_visible_name(instance_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    iaas.update_zabbix_host_visible_name(instance)
