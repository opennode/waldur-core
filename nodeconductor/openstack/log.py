from nodeconductor.logging.log import EventLogger, event_logger


class BackupEventLogger(EventLogger):
    resource = 'structure.Resource'

    class Meta:
        event_types = ('resource_backup_creation_scheduled',
                       'resource_backup_creation_succeeded',
                       'resource_backup_creation_failed',
                       'resource_backup_restoration_scheduled',
                       'resource_backup_restoration_succeeded',
                       'resource_backup_restoration_failed',
                       'resource_backup_deletion_scheduled',
                       'resource_backup_deletion_succeeded',
                       'resource_backup_deletion_failed',
                       'resource_backup_schedule_creation_succeeded',
                       'resource_backup_schedule_update_succeeded',
                       'resource_backup_schedule_deletion_succeeded',
                       'resource_backup_schedule_activated',
                       'resource_backup_schedule_deactivated')


event_logger.register('openstack_backup', BackupEventLogger)
