from nodeconductor.logging.loggers import EventLogger, event_logger


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


class InstanceFlavorChangeEventLogger(EventLogger):
    resource = 'structure.Resource'
    flavor = 'openstack.Flavor'

    class Meta:
        event_types = ('resource_flavor_change_scheduled',
                       'resource_flavor_change_succeeded',
                       'resource_flavor_change_failed')


class InstanceVolumeChangeEventLogger(EventLogger):
    resource = 'structure.Resource'
    volume_size = int

    class Meta:
        nullable_fields = ['volume_size']
        event_types = ('resource_volume_extension_scheduled',
                       'resource_volume_extension_succeeded',
                       'resource_volume_extension_failed')


event_logger.register('openstack_backup', BackupEventLogger)
event_logger.register('openstack_flavor', InstanceFlavorChangeEventLogger)
event_logger.register('openstack_volume', InstanceVolumeChangeEventLogger)
