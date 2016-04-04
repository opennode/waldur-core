from nodeconductor.logging.loggers import EventLogger, event_logger


class ZabbixEventLogger(EventLogger):
    instance = 'iaas.Instance'

    class Meta:
        event_types = (
            'zabbix_host_creation_succeeded',
            'zabbix_host_creation_failed',
            'zabbix_host_deletion_succeeded',
            'zabbix_host_deletion_failed'
        )

event_logger.register('zabbix', ZabbixEventLogger)
