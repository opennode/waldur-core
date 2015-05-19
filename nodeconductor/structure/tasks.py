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


@shared_task(name='nodeconductor.structure.sync_services')
def sync_services(service_uuids=None):
    services = models.Service.objects.filter(state=SynchronizationStates.IN_SYNC)
    if service_uuids and isinstance(service_uuids, (list, tuple)):
        services = services.filter(uuid__in=service_uuids)

    for service in services:
        service.schedule_syncing()
        service.save()

        service_uuid = service.uuid.hex
        sync_service.apply_async(
            args=(service_uuid,),
            link=sync_service_succeeded.si(service_uuid),
            link_error=sync_service_failed.si(service_uuid))


@shared_task
@transition(models.Service, 'begin_syncing')
def sync_service(service_uuid, transition_entity=None):
    service = transition_entity
    backend = service.get_backend()
    backend.sync()


@shared_task
@transition(models.Service, 'set_in_sync')
def sync_service_succeeded(service_uuid, transition_entity=None):
    pass


@shared_task
@transition(models.Service, 'set_erred')
def sync_service_failed(service_uuid, transition_entity=None):
    pass
