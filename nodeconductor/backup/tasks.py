import logging

from celery import shared_task

from nodeconductor.backup import models


logger = logging.getLogger(__name__)


@shared_task
def process_backup_task(backup_uuid):
    try:
        backup = models.Backup.objects.get(uuid=backup_uuid)
        source = backup.backup_source
        if source is not None:
            backup.backup_source.get_backup_strategy().backup()
        else:
            logger.exception('Process backup task was called for backup with no source. Backup uuid: %s', backup_uuid)
    except models.Backup.DoesNotExist:
        logger.exception('Process backup task was called for backed with uuid %s which does not exist', backup_uuid)


@shared_task
def restoration_task(backup_uuid, replace_original=False):
    try:
        backup = models.Backup.objects.get(uuid=backup_uuid)
        source = backup.backup_source
        if source is not None:
            backup.backup_source.get_backup_strategy().restore(replace_original)
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
            backup.backup_source.get_backup_strategy().delete()
        else:
            logger.exception('Restoration task was called for backup with no source. Backup uuid: %s', backup_uuid)
    except models.Backup.DoesNotExist:
        logger.exception('Deletion task was called for backed with uuid %s which does not exist', backup_uuid)
