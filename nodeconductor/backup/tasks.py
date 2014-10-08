from celery import shared_task


@shared_task
def backup_task(backupable_instance):
    backupable_instance.get_backup_strategy.backup()


@shared_task
def restoration_task(backupable_instance, replace_original=False):
    backupable_instance.get_backup_strategy.restore(replace_original)


@shared_task
def deletion_task(backupable_instance):
    backupable_instance.get_backup_strategy.delete()
