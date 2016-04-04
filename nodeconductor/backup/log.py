from nodeconductor.logging.loggers import EventLogger, event_logger


class BackupEventLogger(EventLogger):
    cloud_account = 'iaas.Cloud'
    iaas_instance = 'iaas.Instance'
    customer = 'structure.Customer'
    project = 'structure.Project'

    class Meta:
        event_types = ('iaas_backup_creation_scheduled',
                       'iaas_backup_creation_succeeded',
                       'iaas_backup_creation_failed',
                       'iaas_backup_restoration_scheduled',
                       'iaas_backup_restoration_succeeded',
                       'iaas_backup_restoration_failed',
                       'iaas_backup_deletion_scheduled',
                       'iaas_backup_deletion_succeeded',
                       'iaas_backup_deletion_failed')


class BackupScheduleEventLogger(EventLogger):
    cloud_account = 'iaas.Cloud'
    iaas_instance = 'iaas.Instance'
    customer = 'structure.Customer'
    project = 'structure.Project'

    class Meta:
        event_types = ('iaas_backup_schedule_creation_succeeded',
                       'iaas_backup_schedule_update_succeeded',
                       'iaas_backup_schedule_deletion_succeeded',
                       'iaas_backup_schedule_activated',
                       'iaas_backup_schedule_deactivated')


def extract_event_context(instance):
    context = {'iaas_instance': instance.backup_source}
    cpm = context['iaas_instance'].cloud_project_membership
    context['cloud_account'] = cpm.cloud
    context['project'] = cpm.project
    context['customer'] = context['project'].customer
    return context


event_logger.register('backup', BackupEventLogger)
event_logger.register('backup_schedule', BackupScheduleEventLogger)
