from datetime import timedelta
from mock import patch

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


class PollBackupsCommandTest(TestCase):

    def setUp(self):
        states = models.Backup.States
        self.backuping_backup = factories.BackupFactory(state=states.BACKING_UP, result_id='bid')
        self.restoring_backup = factories.BackupFactory(state=states.RESTORING, result_id='rid')
        self.deleting_backup = factories.BackupFactory(state=states.DELETING, result_id='did')

    def test_command_looks_at_executing_backup_task_result(self):
        with patch('nodeconductor.backup.tasks.process_backup_task.AsyncResult') as patched:
            call_command('poll_backups')
            patched.assert_called_with(self.backuping_backup.result_id)

    def test_command_looks_at_restoring_backup_task_result(self):
        with patch('nodeconductor.backup.tasks.restoration_task.AsyncResult') as patched:
            call_command('poll_backups')
            patched.assert_called_with(self.restoring_backup.result_id)

    def test_command_looks_at_deleting_backup_task_result(self):
        with patch('nodeconductor.backup.tasks.deletion_task.AsyncResult') as patched:
            call_command('poll_backups')
            patched.assert_called_with(self.deleting_backup.result_id)
