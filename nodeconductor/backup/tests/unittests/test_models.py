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
        schedule = factories.BackupScheduleFactory()
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
            backup_schedule=schedule, state=models.Backup.States.BACKING_UP).exists())
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


class BackupTest(TestCase):

    class MockedAsyncResult(object):

        def __call__(self, *args):
            return self if not self._is_none else None

        def __init__(self, ready, is_none=False):
            self._ready = ready
            self._is_none = is_none

        def ready(self):
            return self._ready

    def test_save(self):
        backup = factories.BackupFactory()
        with self.assertRaises(IntegrityError):
            backup.save()

    @patch('nodeconductor.backup.tasks.process_backup_task.delay')
    def test_start_backup(self, mocked_task):
        backup = factories.BackupFactory()
        backup.start_backup()
        mocked_task.assert_called_with(backup.uuid.hex)
        self.assertEqual(backup.state, models.Backup.States.BACKING_UP)

    @patch('nodeconductor.backup.tasks.restoration_task.delay')
    def test_start_restoration(self, mocked_task):
        backup = factories.BackupFactory()
        backup.start_restoration()
        mocked_task.assert_called_with(backup.uuid.hex)
        self.assertEqual(backup.state, models.Backup.States.RESTORING)

    @patch('nodeconductor.backup.tasks.deletion_task.delay')
    def test_start_deletion(self, mocked_task):
        backup = factories.BackupFactory()
        backup.start_deletion()
        mocked_task.assert_called_with(backup.uuid.hex)
        self.assertEqual(backup.state, models.Backup.States.DELETING)
