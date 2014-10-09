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


def _backup_schedule_url(schedule):
    return 'http://testserver' + reverse('backupschedule-detail', args=(str(schedule.uuid), ))


class BackupUsageTest(test.APISimpleTestCase):

    def setUp(self):
        # only for test lets make backupshedule backupable
        backup_registry.BACKUP_REGISTRY = {'Schedule': 'backup_backupschedule'}
        self.user = structure_factories.UserFactory.create(is_staff=True, is_superuser=True)
        self.client.force_authenticate(user=self.user)

    def test_backup_manually_create(self):
        backupable = factories.BackupScheduleFactory()
        backup_data = {
            'backup_source': _backup_schedule_url(backupable),
        }
        url = _backup_list_url()
        response = self.client.post(url, data=backup_data)
        self.assertEqual(response.status_code, 201)
        backup = models.Backup.objects.get(object_id=backupable.id)
        self.assertEqual(backup.state, models.Backup.States.BACKING_UP)

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



