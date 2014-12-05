from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.backup import models
from nodeconductor.backup.tests import factories
from nodeconductor.core.tests import helpers
from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.iaas.tests import factories as iaas_factories


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


class BackupUsageTest(test.APITransactionTestCase):

    def setUp(self):
        self.user = structure_factories.UserFactory.create(is_staff=True, is_superuser=True)
        self.client.force_authenticate(user=self.user)

    def test_backup_manually_create(self):
        # success:
        backupable = iaas_factories.InstanceFactory()
        backup_data = {
            'backup_source': iaas_factories.InstanceFactory.get_url(backupable),
        }
        url = _backup_list_url()
        response = self.client.post(url, data=backup_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        backup = models.Backup.objects.get(object_id=backupable.id)
        self.assertEqual(backup.state, models.Backup.States.BACKING_UP)
        # fail:
        backup_data = {
            'backup_source': 'some_random_url',
        }
        url = _backup_list_url()
        response = self.client.post(url, data=backup_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('backup_source', response.content)

    def test_backup_restore(self):
        backup = factories.BackupFactory()
        url = _backup_url(backup, action='restore')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(models.Backup.objects.get(pk=backup.pk).state, models.Backup.States.RESTORING)

    def test_backup_delete(self):
        backup = factories.BackupFactory()
        url = _backup_url(backup, action='delete')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(models.Backup.objects.get(pk=backup.pk).state, models.Backup.States.DELETING)


class BackupScheduleUsageTest(test.APISimpleTestCase):

    def setUp(self):
        self.user = structure_factories.UserFactory.create(is_staff=True, is_superuser=True)
        self.client.force_authenticate(user=self.user)

    def test_backup_schedule_creation(self):
        backupable = iaas_factories.InstanceFactory()
        backup_schedule_data = {
            'retention_time': 3,
            'backup_source': iaas_factories.InstanceFactory.get_url(backupable),
            'schedule': '*/5 * * * *',
            'maximal_number_of_backups': 3,
        }
        response = self.client.post(_backup_schedule_list_url(), backup_schedule_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['retention_time'], backup_schedule_data['retention_time'])
        self.assertEqual(response.data['maximal_number_of_backups'], backup_schedule_data['maximal_number_of_backups'])
        self.assertEqual(response.data['schedule'], backup_schedule_data['schedule'])
        # wrong schedule:
        backup_schedule_data['schedule'] = 'wrong schedule'
        response = self.client.post(_backup_schedule_list_url(), backup_schedule_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('schedule', response.content)
        # wrong backup source:
        backup_schedule_data['schedule'] = '*/5 * * * *'
        backup = factories.BackupFactory()
        unbackupable_url = 'http://testserver' + reverse('backup-detail', args=(backup.uuid, ))
        backup_schedule_data['backup_source'] = unbackupable_url
        response = self.client.post(_backup_schedule_list_url(), backup_schedule_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('backup_source', response.content)

    def test_schedule_activation_and_deactivation(self):
        schedule = factories.BackupScheduleFactory(is_active=False)
        # activate
        response = self.client.post(_backup_schedule_url(schedule, action='activate'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(models.BackupSchedule.objects.get(pk=schedule.pk).is_active)
        # deactivate
        response = self.client.post(_backup_schedule_url(schedule, action='deactivate'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(models.BackupSchedule.objects.get(pk=schedule.pk).is_active)


class BackupListPermissionsTest(helpers.ListPermissionsTest):

    url = _backup_list_url()

    def get_users_and_expected_results(self):
        instance = iaas_factories.InstanceFactory()
        backup1 = factories.BackupFactory(backup_source=instance)
        backup2 = factories.BackupFactory(backup_source=instance)
        # deleted backup should not be visible even for user with permissions
        factories.BackupFactory(backup_source=instance, state=models.Backup.States.DELETED)

        user_with_view_permission = structure_factories.UserFactory.create(is_staff=True, is_superuser=True)
        user_without_view_permission = structure_factories.UserFactory.create()

        return [
            {
                'user': user_with_view_permission,
                'expected_results': [
                    {'url': _backup_url(backup1)}, {'url': _backup_url(backup2)}
                ]
            },
            {
                'user': user_without_view_permission,
                'expected_results': []
            },
        ]


class BackupPermissionsTest(helpers.PermissionsTest):

    def setUp(self):
        self.user_with_permission = structure_factories.UserFactory.create(is_staff=True, is_superuser=True)
        self.user_without_permission = structure_factories.UserFactory.create()

    def get_users_with_permission(self, url, method):
        return [self.user_with_permission]

    def get_users_without_permissions(self, url, method):
        return [self.user_without_permission]

    def get_urls_configs(self):
        instance = iaas_factories.InstanceFactory()
        backup = factories.BackupFactory(backup_source=instance)
        yield {'url': _backup_url(backup), 'method': 'GET'}
        yield {'url': _backup_url(backup, action='delete'), 'method': 'POST'}
        # we need to recreate backup because previous one was deleted
        backup = factories.BackupFactory()
        yield {'url': _backup_url(backup, action='restore'), 'method': 'POST'}
        instance_url = 'http://testserver' + reverse('instance-detail', args=(str(instance.uuid),))
        yield {'url': _backup_list_url(), 'method': 'POST',
               'data': {'backup_source': instance_url}}


class BackupScheduleListPermissionsTest(helpers.ListPermissionsTest):

    url = _backup_schedule_list_url()

    def get_users_and_expected_results(self):
        instance = iaas_factories.InstanceFactory()
        schedule = factories.BackupScheduleFactory(backup_source=instance)

        user_with_view_permission = structure_factories.UserFactory.create(is_staff=True, is_superuser=True)
        user_without_view_permission = structure_factories.UserFactory.create()

        return [
            {
                'user': user_with_view_permission,
                'expected_results': [
                    {'url': _backup_schedule_url(schedule)}
                ]
            },
            {
                'user': user_without_view_permission,
                'expected_results': []
            },
        ]


class BackupSchedulePermissionsTest(helpers.PermissionsTest):

    def setUp(self):
        super(BackupSchedulePermissionsTest, self).setUp()
        self.user_with_permission = structure_factories.UserFactory.create(is_staff=True, is_superuser=True)
        self.user_without_permission = structure_factories.UserFactory.create()

    def get_users_with_permission(self, url, method):
        return [self.user_with_permission]

    def get_users_without_permissions(self, url, method):
        return [self.user_without_permission]

    def get_urls_configs(self):
        instance = iaas_factories.InstanceFactory()
        schedule = factories.BackupScheduleFactory(backup_source=instance)
        yield {'url': _backup_schedule_url(schedule), 'method': 'GET'}
        yield {'url': _backup_schedule_url(schedule, action='deactivate'), 'method': 'POST'}
        yield {'url': _backup_schedule_url(schedule, action='activate'), 'method': 'POST'}
        yield {'url': _backup_schedule_url(schedule), 'method': 'PATCH'}
        yield {'url': _backup_schedule_url(schedule), 'method': 'PUT'}
        yield {'url': _backup_schedule_url(schedule), 'method': 'DELETE'}
        instance_url = 'http://testserver' + reverse('instance-detail', args=(str(instance.uuid),))
        backup_schedule_data = {
            'retention_time': 3,
            'backup_source': instance_url,
            'schedule': '*/5 * * * *',
            'maximal_number_of_backups': 3,
        }
        yield {'url': _backup_list_url(), 'method': 'POST', 'data': backup_schedule_data}
