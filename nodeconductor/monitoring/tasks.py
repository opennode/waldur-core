from decimal import Decimal
import logging

from celery import shared_task

from nodeconductor.iaas.models import Instance, InstanceSlaHistory
from nodeconductor.monitoring.zabbix.api_client import ZabbixApiClient
from nodeconductor.monitoring.zabbix.errors import ZabbixError

logger = logging.getLogger(__name__)


@shared_task
def update_instance_sla():
    instances = Instance.objects.exclude(state__in=(Instance.States.DELETED, Instance.States.DELETING))
    zabbix_client = ZabbixApiClient()
    for instance in instances:
        try:
            logger.debug('Updating SLAs for instance %s' % instance)
            current_sla = zabbix_client.get_current_service_sla(instance, start_time=1417023243, end_time=1417723243)
            entry, _ = InstanceSlaHistory.objects.get_or_create(
                instance=instance,
                period='12'
            )
            entry.value = Decimal(current_sla)
            entry.save()
        except ZabbixError as e:
            logger.warning('Failed to update current SLA values for %s. Reason: %s' % (instance, e))
