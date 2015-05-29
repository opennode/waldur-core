from __future__ import unicode_literals

import logging

from celery import shared_task

from nodeconductor.core.tasks import transition
from nodeconductor.core.models import SynchronizationStates
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
    if not isinstance(customer_uuids, (list, tuple)):
        customer_uuids = models.Customer.objects.all().values_list('uuid', flat=True)

    map(sync_billing_customer.delay, customer_uuids)


@shared_task
def sync_billing_customer(customer_uuid):
    customer = models.Customer.objects.get(uuid=customer_uuid)
    backend = customer.get_billing_backend()
    backend.sync_customer()
    backend.sync_invoices()


@shared_task(name='nodeconductor.structure.sync_service_settings')
def sync_service_settings(settings_uuids=None):
    settings = models.ServiceSettings.objects.filter(state=SynchronizationStates.IN_SYNC)
    if settings_uuids and isinstance(settings_uuids, (list, tuple)):
        settings = settings.filter(uuid__in=settings_uuids)

    for obj in settings:
        obj.schedule_syncing()
        obj.save()

        settings_uuid = obj.uuid.hex
        begin_syncing_service_settings.apply_async(
            args=(settings_uuid,),
            link=sync_service_settings_succeeded.si(settings_uuid),
            link_error=sync_service_settings_failed.si(settings_uuid))


@shared_task
@transition(models.ServiceSettings, 'begin_syncing')
def begin_syncing_service_settings(settings_uuid, transition_entity=None):
    settings = transition_entity
    backend = settings.get_backend()
    backend.sync()


@shared_task
@transition(models.ServiceSettings, 'set_in_sync')
def sync_service_settings_succeeded(settings_uuid, transition_entity=None):
    pass


@shared_task
@transition(models.ServiceSettings, 'set_erred')
def sync_service_settings_failed(settings_uuid, transition_entity=None):
    pass
