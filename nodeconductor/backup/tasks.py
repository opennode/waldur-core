import logging

from celery import shared_task
from django.utils import timezone

from nodeconductor.backup import models, exceptions
from nodeconductor.backup.log import event_logger, extract_event_context


logger = logging.getLogger(__name__)


@shared_task
def process_backup_task(backup_uuid):
    try:
        backup = models.Backup.objects.get(uuid=backup_uuid)
        source = backup.backup_source
        if source is not None:
            logger.debug('About to perform backup for backup source: %s', backup.backup_source)
            event_logger.backup.info(
                'Backup for {iaas_instance_name} has been scheduled.',
                event_type='iaas_backup_creation_scheduled',
                event_context=extract_event_context(backup))

            try:
                backup.metadata = backup.get_strategy().backup(backup.backup_source)
                backup.confirm_backup()
            except exceptions.BackupStrategyExecutionError:
                schedule = backup.backup_schedule
                if schedule:
                    schedule.is_active = False
                    schedule.save()

                    event_logger.backup_schedule.info(
                        'Backup schedule for {iaas_instance_name} has been deactivated.',
                        event_type='iaas_backup_schedule_deactivated',
                        event_context=extract_event_context(schedule))

                logger.exception('Failed to perform backup for backup source: %s', source.name)
                event_logger.backup.info(
                    'Backup creation for {iaas_instance_name} has failed.',
                    event_type='iaas_backup_creation_failed',
                    event_context=extract_event_context(backup))

                backup.erred()
            else:
                logger.info('Successfully performed backup for backup source: %s', source.name)
                event_logger.backup.info(
                    'Backup for {iaas_instance_name} has been created.',
                    event_type='iaas_backup_creation_succeeded',
                    event_context=extract_event_context(backup))
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
            event_logger.backup.info(
                'Backup restoration for {iaas_instance_name} has been scheduled.',
                event_type='iaas_backup_restoration_scheduled',
                event_context=extract_event_context(backup))
            try:
                backup.get_strategy().restore(instance_uuid, user_raw_input, snapshot_ids)
                backup.confirm_restoration()
            except exceptions.BackupStrategyExecutionError:
                logger.exception('Failed to restore backup for backup source: %s', source)
                event_logger.backup.info(
                    'Backup restoration for {iaas_instance_name} has failed.',
                    event_type='iaas_backup_restoration_failed',
                    event_context=extract_event_context(backup))

                backup.erred()
            else:
                logger.info('Successfully restored backup for backup source: %s', source)
                event_logger.backup.info(
                    'Backup for {iaas_instance_name} has been restored.',
                    event_type='iaas_backup_restoration_succeeded',
                    event_context=extract_event_context(backup))
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
            event_logger.backup.info(
                'Backup deletion for {iaas_instance_name} has been scheduled.',
                event_type='iaas_backup_deletion_scheduled',
                event_context=extract_event_context(backup))

            try:
                backup.get_strategy().delete(source, backup.metadata)
                backup.confirm_deletion()
            except exceptions.BackupStrategyExecutionError:
                logger.exception('Failed to delete backup for backup source: %s', source)
                event_logger.backup.info(
                    'Backup deletion for {iaas_instance_name} has failed.',
                    event_type='iaas_backup_deletion_failed',
                    event_context=extract_event_context(backup))

                backup.erred()
            else:
                logger.info('Successfully deleted backup for backup source: %s', source)
                event_logger.backup.info(
                    'Backup for {iaas_instance_name} has been deleted.',
                    event_type='iaas_backup_deletion_succeeded',
                    event_context=extract_event_context(backup))
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
