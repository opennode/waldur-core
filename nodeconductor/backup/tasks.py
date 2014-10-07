from celery import shared_task


@shared_task
def backup_task(backupable_instance):
    backupable_instance.get_backup_strategy.backup()


@shared_task
def restore_task(backupable_instance):
    backupable_instance.get_backup_strategy.restore()


@shared_task
def delete_task(backupable_instance):
    backupable_instance.get_backup_strategy.delete()
