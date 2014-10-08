from django.core.management.base import NoArgsCommand

from nodeconductor.backup import models


class Command(NoArgsCommand):
    help = 'Looks throught all executing backups and polls their current state'

    def handle_noargs(self, **options):
        states = models.Backup.States
        executing_states = (states.BACKUPING, states.RESTORING, states.DELETING)
        for backup in models.Backup.objects.filter(state__in=executing_states):
            backup.poll_current_state()
