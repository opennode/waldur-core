# -*- coding: utf-8 -*-
from __future__ import absolute_import

from celery import shared_task

from nodeconductor.iaas.models import Instance
from nodeconductor.iaas.tasks.iaas import create_zabbix_host_and_service


@shared_task
def zabbix_create_host_and_service(instance_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    create_zabbix_host_and_service(instance)
