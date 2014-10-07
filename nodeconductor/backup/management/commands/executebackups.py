from django.core.management.base import NoArgsCommand

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

    def handle_noargs(self, **options):
        self._verify_executing_backups()
        models.BackupSchedule.execute_all_schedules()
