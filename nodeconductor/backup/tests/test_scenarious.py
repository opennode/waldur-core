from django.core.urlresolvers import reverse

from rest_framework import test

from nodeconductor.backup import models, backup_registry
from nodeconductor.backup.tests import factories
from nodeconductor.structure.tests import factories as structure_factories


def _backup_url(backup, action=None):
    url = 'http://testserver' + reverse('backup-detail', args=(str(backup.uuid), ))
    return url if action is None else url + action + '/'


def _backup_list_url():
    return 'http://testserver' + reverse('backup-list')


def _backup_schedule_url(schedule, action=None):
    url = 'http://testserver' + reverse('backupschedule-detail', args=(str(schedule.uuid), ))
    return url if action is None else url + action + '/'


def _backup_schedule_list_url():
    return 'http://testserver' + reverse('backupschedule-list')


class BackupUsageTest(test.APISimpleTestCase):

    def setUp(self):
        # only for test lets make backupshedule backupable
        backup_registry.BACKUP_REGISTRY = {'Schedule': 'backup_backupschedule'}
        self.user = structure_factories.UserFactory.create(is_staff=True, is_superuser=True)
        self.client.force_authenticate(user=self.user)

    def test_backup_manually_create(self):
        # success:
        backupable = factories.BackupScheduleFactory()
        backup_data = {
            'backup_source': _backup_schedule_url(backupable),
        }
        url = _backup_list_url()
        response = self.client.post(url, data=backup_data)
        self.assertEqual(response.status_code, 201)
        backup = models.Backup.objects.get(object_id=backupable.id)
        self.assertEqual(backup.state, models.Backup.States.BACKING_UP)
        # fail:
        backup_data = {
            'backup_source': 'some_random_url',
        }
        url = _backup_list_url()
        response = self.client.post(url, data=backup_data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('backup_source', response.content)

    def test_backup_restore(self):
        backup = factories.BackupFactory()
        url = _backup_url(backup, action='restore')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(models.Backup.objects.get(pk=backup.pk).state, models.Backup.States.RESTORING)

    def test_backup_delete(self):
        backup = factories.BackupFactory()
        url = _backup_url(backup, action='delete')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(models.Backup.objects.get(pk=backup.pk).state, models.Backup.States.DELETING)


class BackupScheduleUsageTest(test.APISimpleTestCase):

    def setUp(self):
        # only for test lets make backupshedule backupable
        backup_registry.BACKUP_REGISTRY = {'Schedule': 'backup_backupschedule'}
        self.user = structure_factories.UserFactory.create(is_staff=True, is_superuser=True)
        self.client.force_authenticate(user=self.user)

    def test_backup_schedule_creation(self):
        backupable = factories.BackupScheduleFactory()
        backup_schedule_data = {
            'retention_time': 3,
            'backup_source': _backup_schedule_url(backupable),
            'schedule': '*/5 * * * *',
            'maximal_number_of_backups': 3,
        }
        response = self.client.post(_backup_schedule_list_url(), backup_schedule_data)
        self.assertEqual(response.status_code, 201)
        backup_schedule = models.Backup.objects.get(object_id=backupable.id)
        self.assertEqual(backup_schedule.retention_time, backup_schedule_data['retention_time'])
        self.assertEqual(backup_schedule.maximal_number_of_backups, backup_schedule_data['maximal_number_of_backups'])
        self.assertEqual(backup_schedule.schedule, backup_schedule_data['schedule'])

    def test_schedule_activation_and_deactivation(self):
        schedule = factories.BackupScheduleFactory(is_active=False)
        # activate
        response = self.client.post(_backup_schedule_url(schedule, action='activate'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(models.BackupSchedule.objects.get(pk=schedule.pk).is_active)
        # deactivate
        response = self.client.post(_backup_schedule_url(schedule, action='deactivate'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(models.BackupSchedule.objects.get(pk=schedule.pk).is_active)
