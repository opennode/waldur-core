import logging

from celery import shared_task

from nodeconductor.backup import models, exceptions


logger = logging.getLogger(__name__)


@shared_task
def process_backup_task(backup_uuid):
    try:
        backup = models.Backup.objects.get(uuid=backup_uuid)
        source = backup.backup_source
        if source is not None:
            logger.debug('About to perform backup for backup source: %s', backup.backup_source)
            try:
                additional_data = backup.get_strategy().backup(backup.backup_source)
                backup.set_additional_data(additional_data)
                backup.confirm_backup()
            except exceptions.BackupStrategyExecutionError:
                logger.exception('Failed to perform backup for backup source: %s', backup.backup_source)
                backup._erred()
            else:
                logger.info('Successfully performed backup for backup source: %s', backup.backup_source)
        else:
            logger.exception('Process backup task was called for backup with no source. Backup uuid: %s', backup_uuid)
    except models.Backup.DoesNotExist:
        logger.exception('Process backup task was called for backed with uuid %s which does not exist', backup_uuid)


@shared_task
def restoration_task(backup_uuid):
    try:
        backup = models.Backup.objects.get(uuid=backup_uuid)
        source = backup.backup_source
        if source is not None:
            logger.debug('About to restore backup for backup source: %s', backup.backup_source)
            try:
                backup.get_strategy().restore(backup.backup_source, backup.additional_data)
                backup.confirm_restoration()
            except exceptions.BackupStrategyExecutionError:
                logger.exception('Failed to restore backup for backup source: %s', backup.backup_source)
                backup._erred()
            else:
                logger.info('Successfully restored backup for backup source: %s', backup.backup_source)
        else:
            logger.exception('Restoration task was called for backup with no source. Backup uuid: %s', backup_uuid)
    except models.Backup.DoesNotExist:
        logger.exception('Restoration task was called for backed with uuid %s which does not exist', backup_uuid)


@shared_task
def deletion_task(backup_uuid):
    try:
        backup = models.Backup.objects.get(uuid=backup_uuid)
        source = backup.backup_source
        if source is not None:
            logger.debug('About to delete backup for backup source: %s', backup.backup_source)
            try:
                backup.get_strategy().delete(backup.backup_source, backup.additional_data)
                backup.confirm_deletion()
            except exceptions.BackupStrategyExecutionError:
                logger.exception('Failed to delete backup for backup source: %s', backup.backup_source)
                backup._erred()
            else:
                logger.info('Successfully deleted backup for backup source: %s', backup.backup_source)
        else:
            logger.exception('Restoration task was called for backup with no source. Backup uuid: %s', backup_uuid)
    except models.Backup.DoesNotExist:
        logger.exception('Deletion task was called for backed with uuid %s which does not exist', backup_uuid)
