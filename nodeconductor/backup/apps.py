from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.backup import handlers


class BackupConfig(AppConfig):
    name = 'nodeconductor.backup'
    verbose_name = 'NodeConductor Backup'

    # See, https://docs.djangoproject.com/en/1.7/ref/applications/#django.apps.AppConfig.ready
    def ready(self):
        BackupSchedule = self.get_model('BackupSchedule')

        signals.post_save.connect(
            handlers.log_backup_schedule_save,
            sender=BackupSchedule,
            dispatch_uid='nodeconductor.backup.handlers.log_backup_schedule_save',
        )

        signals.post_delete.connect(
            handlers.log_backup_schedule_delete,
            sender=BackupSchedule,
            dispatch_uid='nodeconductor.backup.handlers.log_backup_schedule_delete',
        )
