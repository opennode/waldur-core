from django.core.management.base import NoArgsCommand
from django.utils import timezone

from nodeconductor.backup import models


class Command(NoArgsCommand):
    help = 'Creates new backups if schedules next_trigger_at time passed'

    def handle_noargs(self, **options):
        for schedule in models.BackupSchedule.objects.filter(is_active=True, next_trigger_at__lt=timezone.now()):
            schedule.execute()
