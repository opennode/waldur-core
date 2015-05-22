from __future__ import unicode_literals

from nodeconductor.backup.log import event_logger, extract_event_context


def log_backup_schedule_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.backup_schedule.info(
            'Backup schedule for {iaas_instance_name} has been created.',
            event_type='iaas_backup_schedule_creation_succeeded',
            event_context=extract_event_context(instance))
    else:
        event_logger.backup_schedule.info(
            'Backup schedule for {iaas_instance_name} has been updated.',
            event_type='iaas_backup_schedule_update_succeeded',
            event_context=extract_event_context(instance))


def log_backup_schedule_delete(sender, instance, **kwargs):
    # In case schedule was deleted in a cascade, backup_source would be None (NC-401)
    if instance.backup_source:
        event_logger.backup_schedule.info(
            'Backup schedule for {iaas_instance_name} has been deleted.',
            event_type='iaas_backup_schedule_deletion_succeeded',
            event_context=extract_event_context(instance))
