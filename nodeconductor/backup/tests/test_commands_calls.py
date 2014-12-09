from datetime import timedelta

from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone

from nodeconductor.backup import models
from nodeconductor.backup.tests import factories


class DeleteExpiredBackupsCommandTest(TestCase):

    def setUp(self):
        self.expired_backup1 = factories.BackupFactory(kept_until=timezone.now() - timedelta(minutes=1))
        self.expired_backup2 = factories.BackupFactory(kept_until=timezone.now() - timedelta(minutes=10))

    def test_command_starts_backend_deletion(self):
        call_command('delete_expired_backups')
        self.assertEqual(models.Backup.objects.get(pk=self.expired_backup1.pk).state, models.Backup.States.DELETING)
        self.assertEqual(models.Backup.objects.get(pk=self.expired_backup2.pk).state, models.Backup.States.DELETING)


class ExecuteScheduleCommandTest(TestCase):

    def setUp(self):
        self.not_active_schedule = factories.BackupScheduleFactory(is_active=False)

        self.schedule_for_execution = factories.BackupScheduleFactory()
        self.schedule_for_execution.next_trigger_at = timezone.now() - timedelta(minutes=10)
        self.schedule_for_execution.save()

        self.future_schedule = factories.BackupScheduleFactory()
        self.future_schedule.next_trigger_at = timezone.now() + timedelta(minutes=2)
        self.future_schedule.save()

    def test_command_does_not_create_backups_created_for_not_active_schedules(self):
        call_command('execute_schedules')
        self.assertEqual(self.not_active_schedule.backups.count(), 0)

    def test_command_create_one_backup_created_for_schedule_with_next_trigger_in_past(self):
        call_command('execute_schedules')
        self.assertEqual(self.schedule_for_execution.backups.count(), 1)

    def test_command_does_not_create_backups_created_for_schedule_with_next_trigger_in_future(self):
        call_command('execute_schedules')
        self.assertEqual(self.future_schedule.backups.count(), 0)
