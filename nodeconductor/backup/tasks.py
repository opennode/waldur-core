import logging

from celery import shared_task

from nodeconductor.backup import models


logger = logging.getLogger(__name__)


@shared_task
def backup_task(backup_uuid):
    try:
        backup = models.Backup.objects.get(uuid=backup_uuid)
        backup.backup_source.get_backup_strategy().backup()
    except models.Backup.DoesNotExist:
        logger.exception('Backup task was called for backed with uuid %s which does not exist', backup_uuid)


@shared_task
def restoration_task(backup_uuid, replace_original=False):
    try:
        backup = models.Backup.objects.get(uuid=backup_uuid)
        backup.backup_source.get_backup_strategy().restore(replace_original)
    except models.Backup.DoesNotExist:
        logger.exception('Restoration task was called for backed with uuid %s which does not exist', backup_uuid)


@shared_task
def deletion_task(backup_uuid):
    try:
        backup = models.Backup.objects.get(uuid=backup_uuid)
        backup.backup_source.get_backup_strategy().delete()
    except models.Backup.DoesNotExist:
        logger.exception('Deletion task was called for backed with uuid %s which does not exist', backup_uuid)
