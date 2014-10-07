from django.core.management.base import NoArgsCommand
from django.utils import timezone

from nodeconductor.backup import models


class Command(NoArgsCommand):
    help = 'Checks current backups states and creates new backups based on backup schedules'

    def _verify_executing_backups(self):
        """
            Looks throught all executing backups and verifies them
        """
        states = models.Backup.States
        for backup in models.Backup.objects.filter(state=states.BACKUPING):
            backup.verify_backup()
        for backup in models.Backup.objects.filter(state=states.RESTORING):
            backup.verify_restore()
        for backup in models.Backup.objects.filter(state=states.DELETING):
            backup.verify_delete()

    def _execute_all_schedules(self):
        """
            Creates new backups if schedules next_trigger_at time passed
        """
        for schedule in models.BackupSchedule.objects.filter(is_active=True, next_trigger_at__lt=timezone.now()):
            schedule.execute()

    def _delete_expired_backups(self):
        """
            Deletes all expired backups
        """
        for backup in models.Backup.objects.filter(kept_until__lt=timezone.now()):
            backup.start_delete()

    def handle_noargs(self, **options):
        self._delete_expired_backups()
        self._verify_executing_backups()
        self._execute_all_schedules()
