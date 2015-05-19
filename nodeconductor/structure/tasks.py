from __future__ import unicode_literals

import logging

from celery import shared_task

from nodeconductor.monitoring.zabbix.api_client import ZabbixApiClient
from nodeconductor.structure import models

logger = logging.getLogger(__name__)


@shared_task
def create_zabbix_hostgroup(project_uuid):
    project = models.Project.objects.get(uuid=project_uuid)
    zabbix_client = ZabbixApiClient()
    zabbix_client.create_hostgroup(project)


@shared_task
def delete_zabbix_hostgroup(project_uuid):
    project = models.Project.objects.get(uuid=project_uuid)
    zabbix_client = ZabbixApiClient()
    zabbix_client.delete_hostgroup(project)


@shared_task(name='nodeconductor.structure.sync_billing_customers')
def sync_billing_customers(customer_uuids=None):
    queryset = models.Customer.objects.all()
    if customer_uuids and isinstance(customer_uuids, (list, tuple)):
        queryset = queryset.filter(uuid__in=customer_uuids)

    for customer in queryset:
        backend = customer.get_billing_backend()
        backend.sync_customer()
