from __future__ import unicode_literals

import logging

from nodeconductor.core.log import EventLoggerAdapter


logger = logging.getLogger(__name__)
event_logger = EventLoggerAdapter(logger)


def log_backup_schedule_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.info(
            'Backup schedule for %s has been created.', instance.backup_source.name,
            extra={'backup_schedule': instance, 'event_type': 'iaas_backup_schedule_creation_succeeded'}
        )
    else:
        event_logger.info(
            'Backup schedule for %s has been updated.', instance.backup_source.name,
            extra={'backup_schedule': instance, 'event_type': 'iaas_backup_schedule_update_succeeded'}
        )


def log_backup_schedule_delete(sender, instance, **kwargs):
    # In case schedule was deleted in a cascade, backup_source would be None (NC-401)
    if instance.backup_source:
        event_logger.info(
            'Backup schedule for %s has been deleted.', instance.backup_source.name,
            extra={'backup_schedule': instance, 'event_type': 'iaas_backup_schedule_deletion_succeeded'}
        )
