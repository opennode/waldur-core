from __future__ import unicode_literals

from datetime import timedelta
from mock import patch, call

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from nodeconductor.openstack.tests import factories
from nodeconductor.openstack import models


class BackupScheduleTest(TestCase):
    def setUp(self):
        self.instance = factories.InstanceFactory(state=models.Instance.States.OFFLINE)

    def test_update_next_trigger_at(self):
        now = timezone.now()
        schedule = factories.BackupScheduleFactory()
        schedule.schedule = '*/10 * * * *'
        schedule.update_next_trigger_at()
        self.assertTrue(schedule.next_trigger_at)
        self.assertGreater(schedule.next_trigger_at, now)

    def test_update_next_trigger_at_with_provided_timezone(self):
        schedule = factories.BackupScheduleFactory(timezone='Europe/London')
        schedule.update_next_trigger_at()

        # next_trigger_at timezone and schedule's timezone must be equal.
        self.assertEqual(schedule.timezone, schedule.next_trigger_at.tzinfo.zone)

    def test_update_next_trigger_at_with_default_timezone(self):
        schedule = factories.BackupScheduleFactory()
        schedule.update_next_trigger_at()

        # If timezone is not provided, default timezone must be set.
        self.assertEqual(settings.TIME_ZONE, schedule.timezone)

    def test_create_backup(self):
        now = timezone.now()
        schedule = factories.BackupScheduleFactory(retention_time=3, instance=self.instance)
        backend = schedule.get_backend()
        backend.create_backup()
        backup = models.Backup.objects.get(backup_schedule=schedule)
        self.assertFalse(backup.kept_until is None)
        self.assertGreater(backup.kept_until, now - timedelta(days=schedule.retention_time))

    def test_execute(self):
        # we have schedule
        schedule = factories.BackupScheduleFactory(maximal_number_of_backups=1, instance=self.instance)
        # with 2 ready backups
        old_backup1 = factories.BackupFactory(backup_schedule=schedule)
        old_backup2 = factories.BackupFactory(backup_schedule=schedule)
        # and 1 deleted
        deleted_backup = factories.BackupFactory(backup_schedule=schedule, state=models.Backup.States.DELETED)

        with patch('celery.app.base.Celery.send_task') as mocked_task:
            backend = schedule.get_backend()
            backend.execute()

            new_backup = models.Backup.objects.filter(
                backup_schedule=schedule, state=models.Backup.States.READY).order_by('created_at').last()

            # after execution old backups have to be deleted
            # new backup have to be created
            mocked_task.assert_has_calls([
                call('nodeconductor.openstack.backup_start_create', (new_backup.uuid.hex,), {}, countdown=2),
                call('nodeconductor.openstack.backup_start_delete', (old_backup1.uuid.hex,), {}, countdown=2),
                call('nodeconductor.openstack.backup_start_delete', (old_backup2.uuid.hex,), {}, countdown=2),
            ], any_order=True)

        # deleted backup have to stay deleted
        self.assertEqual(deleted_backup.state, models.Backup.States.DELETED)
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
