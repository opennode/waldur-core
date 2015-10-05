from __future__ import unicode_literals

from datetime import timedelta
from mock import patch

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from nodeconductor.backup.tests import factories
from nodeconductor.backup import models
from nodeconductor.iaas.models import Instance
from nodeconductor.iaas.tests.factories import InstanceFactory


class BackupScheduleTest(TestCase):
    def setUp(self):
        self.backup_source = InstanceFactory(state=Instance.States.OFFLINE)

    def test_update_next_trigger_at(self):
        now = timezone.now()
        schedule = factories.BackupScheduleFactory()
        schedule.schedule = '*/10 * * * *'
        schedule._update_next_trigger_at()
        self.assertTrue(schedule.next_trigger_at)
        self.assertGreater(schedule.next_trigger_at, now)

    def test_update_next_trigger_at_with_provided_timezone(self):
        schedule = factories.BackupScheduleFactory(timezone='Europe/London')
        schedule._update_next_trigger_at()

        # next_trigger_at timezone and schedule's timezone must be equal.
        self.assertEqual(schedule.timezone, schedule.next_trigger_at.tzinfo.zone)

    def test_update_next_trigger_at_with_default_timezone(self):
        schedule = factories.BackupScheduleFactory()
        schedule._update_next_trigger_at()

        # If timezone is not provided, default timezone must be set.
        self.assertEqual(settings.TIME_ZONE, schedule.timezone)

    def test_create_backup(self):
        now = timezone.now()
        schedule = factories.BackupScheduleFactory(retention_time=3,  backup_source=self.backup_source)
        schedule._create_backup()
        backup = models.Backup.objects.get(backup_schedule=schedule)
        self.assertFalse(backup.kept_until is None)
        self.assertGreater(backup.kept_until, now - timedelta(days=schedule.retention_time))

    def test_execute(self):
        # we have schedule
        schedule = factories.BackupScheduleFactory(maximal_number_of_backups=1, backup_source=self.backup_source)
        # with 2 ready backups
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
        schedule = models.BackupSchedule.objects.get(id=schedule.id)
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

    @patch('nodeconductor.backup.tasks.process_backup_task.delay')
    def test_start_backup(self, mocked_task):
        backup = factories.BackupFactory()
        backup.start_backup()
        mocked_task.assert_called_with(backup.uuid.hex)
        self.assertEqual(backup.state, models.Backup.States.BACKING_UP)

    @patch('nodeconductor.backup.tasks.restoration_task.delay')
    def test_start_restoration(self, mocked_task):
        backup = factories.BackupFactory()
        # TODO: remove dependency on iaas module
        from nodeconductor.iaas.tests import factories as iaas_factories

        instance = iaas_factories.InstanceFactory()
        user_input = {}
        snapshot_ids = []
        backup.start_restoration(instance.uuid, user_input, snapshot_ids)
        mocked_task.assert_called_with(backup.uuid.hex, instance.uuid.hex, user_input, snapshot_ids)
        self.assertEqual(backup.state, models.Backup.States.RESTORING)

    @patch('nodeconductor.backup.tasks.deletion_task.delay')
    def test_start_deletion(self, mocked_task):
        backup = factories.BackupFactory()
        backup.start_deletion()
        mocked_task.assert_called_with(backup.uuid.hex)
        self.assertEqual(backup.state, models.Backup.States.DELETING)
