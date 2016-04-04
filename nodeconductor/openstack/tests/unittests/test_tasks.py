import mock

from datetime import timedelta
from django.test import TestCase
from django.utils import timezone

from nodeconductor.openstack import tasks
from nodeconductor.openstack.backend import OpenStackBackendError
from nodeconductor.openstack.models import Instance
from nodeconductor.openstack.tests import factories


@mock.patch('nodeconductor.openstack.tasks.instance.throttle')
@mock.patch('nodeconductor.structure.models.Service.get_backend')
class ErrorMessageTest(TestCase):

    def setUp(self):
        self.instance = factories.InstanceFactory()
        self.error = OpenStackBackendError('Unable to find network')

    def test_if_instance_provision_fails_error_message_is_saved(self, mock_backend, mock_throttle):
        mock_backend().provision_instance.side_effect = self.error

        with self.assertRaises(OpenStackBackendError):
            tasks.provision_instance(self.instance.uuid.hex)

        self.assert_instance_has_error_message()

    def test_if_instance_start_fails_error_message_is_saved(self, mock_backend, mock_throttle):
        self.instance.state = Instance.States.STARTING_SCHEDULED
        self.instance.save()
        mock_backend().start_instance.side_effect = self.error

        with self.assertRaises(OpenStackBackendError):
            tasks.start_instance(self.instance.uuid.hex)

        self.assert_instance_has_error_message()

    def test_if_instance_stop_fails_error_message_is_saved(self, mock_backend, mock_throttle):
        self.instance.state = Instance.States.STOPPING_SCHEDULED
        self.instance.save()
        mock_backend().stop_instance.side_effect = self.error

        with self.assertRaises(OpenStackBackendError):
            tasks.stop_instance(self.instance.uuid.hex)

        self.assert_instance_has_error_message()

    def test_if_instance_restart_fails_error_message_is_saved(self, mock_backend, mock_throttle):
        self.instance.state = Instance.States.RESTARTING_SCHEDULED
        self.instance.save()
        mock_backend().restart_instance.side_effect = self.error

        with self.assertRaises(OpenStackBackendError):
            tasks.restart_instance(self.instance.uuid.hex)

        self.assert_instance_has_error_message()

    def test_if_instance_destroy_fails_error_message_is_saved(self, mock_backend, mock_throttle):
        self.instance.state = Instance.States.DELETION_SCHEDULED
        self.instance.save()
        mock_backend().delete_instance.side_effect = self.error

        with self.assertRaises(OpenStackBackendError):
            tasks.destroy_instance(self.instance.uuid.hex)

        self.assert_instance_has_error_message()

    def assert_instance_has_error_message(self):
        instance = Instance.objects.get(pk=self.instance.pk)
        self.assertEqual(instance.error_message, str(self.error))


@mock.patch('celery.app.base.Celery.send_task')
class BackupTest(TestCase):

    def assert_task_called(self, task, name, *args, **kawargs):
        task.assert_has_calls([mock.call(name, args, kawargs, countdown=2)], any_order=True)

    def test_start_backup(self, mocked_task):
        backup = factories.BackupFactory()
        backend = backup.get_backend()
        backend.start_backup()
        self.assert_task_called(mocked_task,
                                'nodeconductor.openstack.backup_start_create',
                                backup.uuid.hex)

    def test_start_restoration(self, mocked_task):
        backup = factories.BackupFactory()
        instance = factories.InstanceFactory()
        user_input = {}
        snapshot_ids = []

        backend = backup.get_backend()
        backend.start_restoration(instance.uuid.hex, user_input, snapshot_ids)
        self.assert_task_called(mocked_task,
                                'nodeconductor.openstack.backup_start_restore',
                                backup.uuid.hex, instance.uuid.hex, user_input, snapshot_ids)

    def test_start_deletion(self, mocked_task):
        backup = factories.BackupFactory()
        backend = backup.get_backend()
        backend.start_deletion()

        self.assert_task_called(mocked_task,
                                'nodeconductor.openstack.backup_start_delete',
                                backup.uuid.hex)


class DeleteExpiredBackupsTaskTest(TestCase):

    def setUp(self):
        self.expired_backup1 = factories.BackupFactory(kept_until=timezone.now() - timedelta(minutes=1))
        self.expired_backup2 = factories.BackupFactory(kept_until=timezone.now() - timedelta(minutes=10))

    @mock.patch('celery.app.base.Celery.send_task')
    def test_command_starts_backend_deletion(self, mocked_task):
        tasks.delete_expired_backups()
        mocked_task.assert_has_calls([
            mock.call('nodeconductor.openstack.backup_start_delete', (self.expired_backup1.uuid.hex,), {}, countdown=2),
            mock.call('nodeconductor.openstack.backup_start_delete', (self.expired_backup2.uuid.hex,), {}, countdown=2),
        ], any_order=True)


class ExecuteScheduleTaskTest(TestCase):

    def setUp(self):
        self.not_active_schedule = factories.BackupScheduleFactory(is_active=False)

        backupable = factories.InstanceFactory(state=Instance.States.OFFLINE)
        self.schedule_for_execution = factories.BackupScheduleFactory(instance=backupable)
        self.schedule_for_execution.next_trigger_at = timezone.now() - timedelta(minutes=10)
        self.schedule_for_execution.save()

        self.future_schedule = factories.BackupScheduleFactory()
        self.future_schedule.next_trigger_at = timezone.now() + timedelta(minutes=2)
        self.future_schedule.save()

    def test_command_does_not_create_backups_created_for_not_active_schedules(self):
        tasks.schedule_backups()
        self.assertEqual(self.not_active_schedule.backups.count(), 0)

    def test_command_create_one_backup_created_for_schedule_with_next_trigger_in_past(self):
        tasks.schedule_backups()
        self.assertEqual(self.schedule_for_execution.backups.count(), 1)

    def test_command_does_not_create_backups_created_for_schedule_with_next_trigger_in_future(self):
        tasks.schedule_backups()
        self.assertEqual(self.future_schedule.backups.count(), 0)
