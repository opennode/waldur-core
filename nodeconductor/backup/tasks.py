from celery import shared_task

from nodeconductor.backup import models


@shared_task
def backup_task(backup_uuid):
    backup = models.Backup.objects.get(uuid=backup_uuid)
    backup.backup_source.get_backup_strategy().backup()


@shared_task
def restoration_task(backup_uuid, replace_original=False):
    backup = models.Backup.objects.get(uuid=backup_uuid)
    backup.backup_source.get_backup_strategy().restore(replace_original)


@shared_task
def deletion_task(backup_uuid):
    backup = models.Backup.objects.get(uuid=backup_uuid)
    backup.backup_source.get_backup_strategy().delete()
