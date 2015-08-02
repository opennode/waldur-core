import logging

from nodeconductor.monitoring.log import event_logger
from nodeconductor.monitoring.zabbix.api_client import ZabbixApiClient
from nodeconductor.monitoring.zabbix.errors import ZabbixError

logger = logging.getLogger(__name__)


def create_host(cloud_project_membership, warn_if_exists=True):
    try:
        zabbix_client = ZabbixApiClient()
        zabbix_client.create_host(
            cloud_project_membership.tenant_id, warn_if_host_exists=warn_if_exists, is_tenant=True)
    except ZabbixError as e:
        # task does not have to fail if something is wrong with zabbix
        logger.error('Zabbix host creation flow has broken %s' % e, exc_info=1)


def create_host_and_service(instance, warn_if_exists=True):
    try:
        zabbix_client = ZabbixApiClient()
        zabbix_client.create_host(instance, warn_if_host_exists=warn_if_exists)
        zabbix_client.create_service(instance, warn_if_service_exists=warn_if_exists)
    except ZabbixError as e:
        # task does not have to fail if something is wrong with zabbix
        logger.error('Zabbix host creation flow has broken %s' % e, exc_info=1)
        event_logger.zabbix.error(
            'Unable to add instance {instance_name} to Zabbix',
            event_type='zabbix_host_creation_failed',
            event_context={'instance': instance}
        )
    else:
        event_logger.zabbix.info(
            'Added instance {instance_name} to Zabbix',
            event_type='zabbix_host_creation_succeeded',
            event_context={'instance': instance}
        )


def delete_host_and_service(instance):
    try:
        zabbix_client = ZabbixApiClient()
        zabbix_client.delete_host(instance)
        zabbix_client.delete_service(instance)
    except ZabbixError as e:
        # task does not have to fail if something is wrong with zabbix
        logger.error('Zabbix host deletion flow has broken %s' % e, exc_info=1)
        event_logger.zabbix.error(
            'Unable to delete instance {instance_name} from Zabbix',
            event_type='zabbix_host_deletion_failed',
            event_context={'instance': instance}
        )
    else:
        event_logger.zabbix.info(
            'Deleted instance {instance_name} from Zabbix',
            event_type='zabbix_host_deletion_succeeded',
            event_context={'instance': instance}
        )
