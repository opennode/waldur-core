import logging

from celery import shared_task
from django.utils import timezone

from nodeconductor.backup import models, exceptions
from nodeconductor.core.log import EventLoggerAdapter


logger = logging.getLogger(__name__)
event_logger = EventLoggerAdapter(logger)


@shared_task
def process_backup_task(backup_uuid):
    try:
        backup = models.Backup.objects.get(uuid=backup_uuid)
        source = backup.backup_source
        if source is not None:
            logger.debug('About to perform backup for backup source: %s', backup.backup_source)
            event_logger.info(
                'Backup for %s has been scheduled.', source.name,
                extra={'backup': backup, 'event_type': 'iaas_backup_creation_scheduled'},
            )
            try:
                backup.metadata = backup.get_strategy().backup(backup.backup_source)
                backup.confirm_backup()
            except exceptions.BackupStrategyExecutionError:
                schedule = backup.backup_schedule
                if schedule:
                    schedule.is_active = False
                    schedule.save()
                    event_logger.info(
                        'Backup schedule for %s has been deactivated.', source.name,
                        extra={'backup_schedule': schedule, 'event_type': 'iaas_backup_schedule_deactivated'}
                    )

                logger.exception('Failed to perform backup for backup source: %s', source.name)
                event_logger.error('Backup creation for %s has failed.', source.name,
                                   extra={'backup': backup, 'event_type': 'iaas_backup_creation_failed'})
                backup.erred()
            else:
                logger.info('Successfully performed backup for backup source: %s', source.name)
                event_logger.info('Backup for %s has been created.', source.name,
                                  extra={'backup': backup, 'event_type': 'iaas_backup_creation_succeeded'})
        else:
            logger.exception('Process backup task was called for backup with no source. Backup uuid: %s', backup_uuid)
    except models.Backup.DoesNotExist:
        logger.exception('Process backup task was called for backed with uuid %s which does not exist', backup_uuid)


@shared_task
def restoration_task(backup_uuid, instance_uuid, user_raw_input, snapshot_ids):
    try:
        backup = models.Backup.objects.get(uuid=backup_uuid)
        source = backup.backup_source
        if source is not None:
            logger.debug('About to restore backup for backup source: %s', source)
            event_logger.info(
                'Backup restoration for %s has been scheduled.', source.name,
                extra={'backup': backup, 'event_type': 'iaas_backup_restoration_scheduled'},
            )
            try:
                backup.get_strategy().restore(instance_uuid, user_raw_input, snapshot_ids)
                backup.confirm_restoration()
            except exceptions.BackupStrategyExecutionError:
                logger.exception('Failed to restore backup for backup source: %s', source)
                event_logger.error('Backup restoration for %s has failed.', source.name,
                                   extra={'backup': backup, 'event_type': 'iaas_backup_restoration_failed'})
                backup.erred()
            else:
                logger.info('Successfully restored backup for backup source: %s', source)
                event_logger.info('Backup for %s has been restored.', source.name,
                                  extra={'backup': backup, 'event_type': 'iaas_backup_restoration_succeeded'})
        else:
            logger.error('Restoration task was called for backup with no source. Backup uuid: %s', backup_uuid)
    except models.Backup.DoesNotExist:
        logger.exception('Restoration task was called for backed with uuid %s which does not exist', backup_uuid)


@shared_task
def deletion_task(backup_uuid):
    try:
        backup = models.Backup.objects.get(uuid=backup_uuid)
        source = backup.backup_source
        if source is not None:
            logger.debug('About to delete backup for backup source: %s', source)
            event_logger.info(
                'Backup deletion for %s has been scheduled.', source.name,
                extra={'backup': backup, 'event_type': 'iaas_backup_deletion_scheduled'},
            )
            try:
                backup.get_strategy().delete(source, backup.metadata)
                backup.confirm_deletion()
            except exceptions.BackupStrategyExecutionError:
                logger.exception('Failed to delete backup for backup source: %s', source)
                event_logger.error('Backup deletion for %s has failed.', source.name,
                                   extra={'backup': backup, 'event_type': 'iaas_backup_deletion_failed'})
                backup.erred()
            else:
                logger.info('Successfully deleted backup for backup source: %s', source)
                event_logger.info('Backup for %s has been deleted.', source.name,
                                  extra={'backup': backup, 'event_type': 'iaas_backup_deletion_succeeded'})
        else:
            logger.error('Deletion task was called for backup with no source. Backup uuid: %s', backup_uuid)
    except models.Backup.DoesNotExist:
        logger.exception('Deletion task was called for backed with uuid %s which does not exist', backup_uuid)


@shared_task
def execute_schedules():
    for schedule in models.BackupSchedule.objects.filter(is_active=True, next_trigger_at__lt=timezone.now()):
        schedule.execute()


@shared_task
def delete_expired_backups():
    for backup in models.Backup.objects.filter(kept_until__lt=timezone.now(), state=models.Backup.States.READY):
        backup.start_deletion()
