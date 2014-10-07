from __future__ import unicode_literals

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from mock import patch

from nodeconductor.backup.tests import factories
from nodeconductor.backup import models
from nodeconductor.backup.management.commands.executebackups import Command


class ExecuteBackupsTest(TestCase):

    def setUp(self):
        self.command = Command()

    def test_verify_executing_backups(self):
        states = models.Backup.States
        backuping_backup = factories.BackupFactory(state=states.BACKUPING, result_id='bid')
        restoring_backup = factories.BackupFactory(state=states.RESTORING, result_id='rid')
        deleting_backup = factories.BackupFactory(state=states.DELETING, result_id='did')

        with patch('nodeconductor.backup.tasks.backup_task.AsyncResult') as patched:
            self.command._verify_executing_backups()
            patched.assert_called_with(backuping_backup.result_id)
        with patch('nodeconductor.backup.tasks.restore_task.AsyncResult') as patched:
            self.command._verify_executing_backups()
            patched.assert_called_with(restoring_backup.result_id)
        with patch('nodeconductor.backup.tasks.delete_task.AsyncResult') as patched:
            self.command._verify_executing_backups()
            patched.assert_called_with(deleting_backup.result_id)

    def test_delete_expired_backups(self):
        expired_backup = factories.BackupFactory(kept_until=timezone.now() - timedelta(minutes=1))

        self.command._delete_expired_backups()

        self.assertEqual(models.Backup.objects.get(pk=expired_backup.pk).state, models.Backup.States.DELETING)

    def test_execute_all_schedules(self):
        not_active_schedule = factories.BackupScheduleFactory(is_active=False)
        schedule_for_execution = factories.BackupScheduleFactory()
        schedule_for_execution.next_trigger_at = timezone.now() - timedelta(minutes=1)
        schedule_for_execution.save()
        future_schedule = factories.BackupScheduleFactory()
        future_schedule.next_trigger_at = timezone.now() + timedelta(minutes=2)
        future_schedule.save()

        self.command._execute_all_schedules()

        self.assertEqual(future_schedule.backups.count(), 0)
        self.assertEqual(schedule_for_execution.backups.count(), 1)
        self.assertEqual(not_active_schedule.backups.count(), 0)
