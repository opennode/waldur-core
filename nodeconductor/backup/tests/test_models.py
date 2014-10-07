from __future__ import unicode_literals

from datetime import timedelta
from mock import patch

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from nodeconductor.backup.tests import factories
from nodeconductor.backup import models


class BackupScheduleTest(TestCase):

    def test_update_next_trigger_at(self):
        now = timezone.now()
        schedule = factories.BackupScheduleFactory.build()
        schedule.schedule = '*/10 * * * *'
        schedule._update_next_trigger_at()
        self.assertTrue(schedule.next_trigger_at)
        self.assertGreater(schedule.next_trigger_at, now)

    def test_create_backup(self):
        now = timezone.now()
        schedule = factories.BackupScheduleFactory(retention_time=3)
        schedule._create_backup()
        backup = models.Backup.objects.get(backup_schedule=schedule)
        self.assertFalse(backup.kept_until is None)
        self.assertGreater(backup.kept_until, now - timedelta(days=schedule.retention_time))

    def test_execute(self):
        # we have schedule
        schedule = factories.BackupScheduleFactory(maximal_number_of_backups=1)
        # with 2 backups ready backups
        old_backup1 = factories.BackupFactory(backup_schedule=schedule)
        old_backup2 = factories.BackupFactory(backup_schedule=schedule)
        # and 1 deleted
        deleted_backup = factories.BackupFactory(backup_schedule=schedule, state=models.Backup.States.DELETED)

        schedule.execute()
        # after execution old backups have to be deleted
        old_backup1 = models.Backup.objects.get(pk=old_backup1.pk)
        self.assertEqual(old_backup1.state, models.Backup.States.DELETING)
        old_backup2 = models.Backup.objects.get(pk=old_backup2.pk)
        self.assertEqual(old_backup2.state, models.Backup.States.DELETING)
        # deleted backup have to stay deleted
        self.assertEqual(deleted_backup.state, models.Backup.States.DELETED)
        # new backup have to be created
        self.assertTrue(models.Backup.objects.filter(
            backup_schedule=schedule, state=models.Backup.States.BACKUPING).exists())
        # and schedule time have to be changed
        self.assertGreater(schedule.next_trigger_at, timezone.now())

    def test_save(self):
        # new schedule
        schedule = factories.BackupScheduleFactory(next_trigger_at=None)
        self.assertGreater(schedule.next_trigger_at, timezone.now())
        # schedule become active
        schedule.is_active = False
        schedule.next_trigger_at = None
        schedule.save()
        schedule.is_active = True
        schedule.save()
        self.assertGreater(schedule.next_trigger_at, timezone.now())
        # schedule was changed
        schedule.next_trigger_at = None
        schedule.schedule = '*/10 * * * *'
        schedule.save()
        self.assertGreater(schedule.next_trigger_at, timezone.now())

    def test_execute_all_schedules(self):
        not_active_schedule = factories.BackupScheduleFactory(is_active=False)
        schedule_for_execution = factories.BackupScheduleFactory()
        schedule_for_execution.next_trigger_at = timezone.now() - timedelta(minutes=1)
        schedule_for_execution.save()
        future_schedule = factories.BackupScheduleFactory()
        future_schedule.next_trigger_at = timezone.now() + timedelta(minutes=2)
        future_schedule.save()
        expired_backup = factories.BackupFactory(kept_until=timezone.now() - timedelta(minutes=1))

        models.BackupSchedule.execute_all_schedules()

        self.assertEqual(not_active_schedule.backups.count(), 0)
        self.assertEqual(future_schedule.backups.count(), 0)
        self.assertEqual(schedule_for_execution.backups.count(), 1)
        self.assertEqual(models.Backup.objects.get(pk=expired_backup.pk).state, models.Backup.States.DELETING)


class BackupTest(TestCase):

    mocked_task_result = type(str('MockedTaskResult'), (object, ), {'id': 'result_id'})

    class MockedAsyncResult(object):

        def __init__(self, ready):
            self._ready = ready

        def ready(self):
            return self._ready

    def test_save(self):
        backup = factories.BackupFactory()
        with self.assertRaises(IntegrityError):
            backup.save()

    @patch('nodeconductor.backup.tasks.backup_task.delay', return_value=mocked_task_result)
    def test_start_backup(self, mocked_task):
        backup = factories.BackupFactory()
        backup.start_backup()
        mocked_task.assert_called_with(backup.backup_source)
        self.assertEqual(backup.result_id, BackupTest.mocked_task_result().id)
        self.assertEqual(backup.state, models.Backup.States.BACKUPING)

    @patch('nodeconductor.backup.tasks.restore_task.delay', return_value=mocked_task_result)
    def test_start_restore(self, mocked_task):
        backup = factories.BackupFactory()
        backup.start_restore()
        mocked_task.assert_called_with(backup.backup_source)
        self.assertEqual(backup.result_id, BackupTest.mocked_task_result().id)
        self.assertEqual(backup.state, models.Backup.States.RESTORING)

    @patch('nodeconductor.backup.tasks.delete_task.delay', return_value=mocked_task_result)
    def test_start_delete(self, mocked_task):
        backup = factories.BackupFactory()
        backup.start_delete()
        mocked_task.assert_called_with(backup.backup_source)
        self.assertEqual(backup.result_id, BackupTest.mocked_task_result().id)
        self.assertEqual(backup.state, models.Backup.States.DELETING)

    def test_verify_backup(self):
        with patch('nodeconductor.backup.tasks.backup_task.AsyncResult',
                   return_value=self.MockedAsyncResult(True)) as mocked_result:
            backup = factories.BackupFactory(result_id='result_id', state=models.Backup.States.BACKUPING)
            backup.verify_backup()
            self.assertEqual(backup.state, models.Backup.States.READY)
            mocked_result.assert_called_with(backup.result_id)

        with patch('nodeconductor.backup.tasks.backup_task.AsyncResult',
                   return_value=self.MockedAsyncResult(False)) as mocked_result:
            backup = factories.BackupFactory(result_id='result_id', state=models.Backup.States.BACKUPING)
            backup.verify_backup()
            self.assertEqual(backup.state, models.Backup.States.BACKUPING)
            mocked_result.assert_called_with(backup.result_id)

    def test_verify_restore(self):
        with patch('nodeconductor.backup.tasks.restore_task.AsyncResult',
                   return_value=self.MockedAsyncResult(True)) as mocked_result:
            backup = factories.BackupFactory(result_id='result_id', state=models.Backup.States.RESTORING)
            backup.verify_restore()
            self.assertEqual(backup.state, models.Backup.States.READY)
            mocked_result.assert_called_with(backup.result_id)

        with patch('nodeconductor.backup.tasks.restore_task.AsyncResult',
                   return_value=self.MockedAsyncResult(False)) as mocked_result:
            backup = factories.BackupFactory(result_id='result_id', state=models.Backup.States.RESTORING)
            backup.verify_restore()
            self.assertEqual(backup.state, models.Backup.States.RESTORING)
            mocked_result.assert_called_with(backup.result_id)

    def test_verify_delete(self):
        with patch('nodeconductor.backup.tasks.delete_task.AsyncResult',
                   return_value=self.MockedAsyncResult(True)) as mocked_result:
            backup = factories.BackupFactory(result_id='result_id', state=models.Backup.States.DELETING)
            backup.verify_delete()
            self.assertEqual(backup.state, models.Backup.States.DELETED)
            mocked_result.assert_called_with(backup.result_id)

        with patch('nodeconductor.backup.tasks.delete_task.AsyncResult',
                   return_value=self.MockedAsyncResult(False)) as mocked_result:
            backup = factories.BackupFactory(result_id='result_id', state=models.Backup.States.DELETING)
            backup.verify_delete()
            self.assertEqual(backup.state, models.Backup.States.DELETING)
            mocked_result.assert_called_with(backup.result_id)
