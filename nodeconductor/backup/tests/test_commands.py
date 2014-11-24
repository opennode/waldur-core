from __future__ import unicode_literals

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from mock import patch

from nodeconductor.backup.tests import factories
from nodeconductor.backup import models
from nodeconductor.backup.management.commands import (
    delete_expired_backups, execute_schedules, poll_backups)


class DeleteExpiredBackupsTest(TestCase):

    def test_handle_noargs(self):
        command = delete_expired_backups.Command()
        expired_backup = factories.BackupFactory(kept_until=timezone.now() - timedelta(minutes=1))
        command.handle_noargs()
        self.assertEqual(models.Backup.objects.get(pk=expired_backup.pk).state, models.Backup.States.DELETING)


class ExecuteScheduleTest(TestCase):

    def test_handle_noargs(self):
        command = execute_schedules.Command()
        not_active_schedule = factories.BackupScheduleFactory(is_active=False)
        schedule_for_execution = factories.BackupScheduleFactory()
        schedule_for_execution.next_trigger_at = timezone.now() - timedelta(minutes=1)
        schedule_for_execution.save()
        future_schedule = factories.BackupScheduleFactory()
        future_schedule.next_trigger_at = timezone.now() + timedelta(minutes=2)
        future_schedule.save()

        command.handle_noargs()

        self.assertEqual(future_schedule.backups.count(), 0)
        self.assertEqual(schedule_for_execution.backups.count(), 1)
        self.assertEqual(not_active_schedule.backups.count(), 0)


class PollBackups(TestCase):

    def test_handle_noargs(self):
        command = poll_backups.Command()
        states = models.Backup.States
        backuping_backup = factories.BackupFactory(state=states.BACKING_UP, result_id='bid')
        restoring_backup = factories.BackupFactory(state=states.RESTORING, result_id='rid')
        deleting_backup = factories.BackupFactory(state=states.DELETING, result_id='did')

        with patch('nodeconductor.backup.tasks.process_backup_task.AsyncResult') as patched:
            command.handle_noargs()
            patched.assert_called_with(backuping_backup.result_id)
        with patch('nodeconductor.backup.tasks.restoration_task.AsyncResult') as patched:
            command.handle_noargs()
            patched.assert_called_with(restoring_backup.result_id)
        with patch('nodeconductor.backup.tasks.deletion_task.AsyncResult') as patched:
            command.handle_noargs()
            patched.assert_called_with(deleting_backup.result_id)
