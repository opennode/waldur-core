from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals


class BackupConfig(AppConfig):
    name = 'nodeconductor.backup'
    verbose_name = 'NodeConductor Backup'

    def ready(self):
        from nodeconductor.backup import handlers

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
