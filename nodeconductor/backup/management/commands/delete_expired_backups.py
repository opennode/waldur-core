from django.core.management.base import NoArgsCommand
from django.utils import timezone

from nodeconductor.backup import models


class Command(NoArgsCommand):
    help = 'Deletes all expired backups'

    def handle_noargs(self):
        for backup in models.Backup.objects.filter(kept_until__lt=timezone.now()):
            backup.start_deletion()
