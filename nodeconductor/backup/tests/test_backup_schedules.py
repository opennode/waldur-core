from __future__ import unicode_literals

import unittest

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.backup import models
from nodeconductor.backup.tests import factories
from nodeconductor.core.tests import helpers
from nodeconductor.iaas.tests import factories as iaas_factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


def _backup_list_url():
    return 'http://testserver' + reverse('backup-list')


def _backup_schedule_url(schedule, action=None):
    url = 'http://testserver' + reverse('backupschedule-detail', args=(str(schedule.uuid), ))
    return url if action is None else url + action + '/'


def _backup_schedule_list_url():
    return 'http://testserver' + reverse('backupschedule-list')


class BackupScheduleUsageTest(test.APISimpleTestCase):

    def setUp(self):
        self.user = structure_factories.UserFactory.create(is_staff=True)
        self.client.force_authenticate(user=self.user)
        backupable = iaas_factories.InstanceFactory()
        self.backup_schedule_data = {
            'retention_time': 3,
            'backup_source': iaas_factories.InstanceFactory.get_url(backupable),
            'schedule': '*/5 * * * *',
            'maximal_number_of_backups': 3,
        }

    def test_staff_can_create_backup_schedule(self):
        response = self.client.post(_backup_schedule_list_url(), self.backup_schedule_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['retention_time'], self.backup_schedule_data['retention_time'])
        self.assertEqual(
            response.data['maximal_number_of_backups'], self.backup_schedule_data['maximal_number_of_backups'])
        self.assertEqual(response.data['schedule'], self.backup_schedule_data['schedule'])

    @unittest.skip('This test should pass after CronField refactoring (NC-443).')
    def test_backup_schedule_can_not_be_created_with_wrong_schedule(self):
        # wrong schedule:
        self.backup_schedule_data['schedule'] = 'wrong schedule'
        response = self.client.post(_backup_schedule_list_url(), self.backup_schedule_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('schedule', response.content)

    def test_backup_schedule_can_not_be_created_with_wrong_source(self):
        # wrong backup source:
        self.backup_schedule_data['schedule'] = '*/5 * * * *'
        backup = factories.BackupFactory()
        unbackupable_url = 'http://testserver' + reverse('backup-detail', args=(backup.uuid, ))
        self.backup_schedule_data['backup_source'] = unbackupable_url
        response = self.client.post(_backup_schedule_list_url(), self.backup_schedule_data)
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

    def test_backup_schedule_do_not_start_activation_of_active_schedule(self):
        schedule = factories.BackupScheduleFactory(is_active=True)
        response = self.client.post(_backup_schedule_url(schedule, action='activate'))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_backup_schedule_do_not_start_deactivation_of_not_active_schedule(self):
        schedule = factories.BackupScheduleFactory(is_active=False)
        response = self.client.post(_backup_schedule_url(schedule, action='deactivate'))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)


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
        # objects
        self.customer = structure_factories.CustomerFactory()
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project_group = structure_factories.ProjectGroupFactory(customer=self.customer)
        self.project_group.projects.add(self.project)
        self.cloud = iaas_factories.CloudFactory(customer=self.customer)
        self.cpm = iaas_factories.CloudProjectMembershipFactory(cloud=self.cloud, project=self.project)
        self.instance = iaas_factories.InstanceFactory(cloud_project_membership=self.cpm)
        self.schedule = factories.BackupScheduleFactory(backup_source=self.instance)
        # users
        self.staff = structure_factories.UserFactory(username='staff', is_staff=True)
        self.regular_user = structure_factories.UserFactory(username='regular user')
        self.project_admin = structure_factories.UserFactory(username='admin')
        self.project.add_user(self.project_admin, structure_models.ProjectRole.ADMINISTRATOR)
        self.customer_owner = structure_factories.UserFactory(username='owner')
        self.customer.add_user(self.customer_owner, structure_models.CustomerRole.OWNER)
        self.project_group_manager = structure_factories.UserFactory(username='manager')
        self.project_group.add_user(self.project_group_manager, structure_models.ProjectGroupRole.MANAGER)

    def get_users_with_permission(self, url, method):
        if method == 'GET':
            return [self.staff, self.project_admin, self.project_group_manager, self.customer_owner]
        else:
            return [self.staff, self.project_admin]

    def get_users_without_permissions(self, url, method):
        if method == 'GET':
            return [self.regular_user]
        else:
            return [self.regular_user, self.project_group_manager, self.customer_owner]

    def get_urls_configs(self):
        yield {'url': _backup_schedule_url(self.schedule), 'method': 'GET'}
        yield {'url': _backup_schedule_url(self.schedule, action='deactivate'), 'method': 'POST'}
        yield {'url': _backup_schedule_url(self.schedule, action='activate'), 'method': 'POST'}
        yield {'url': _backup_schedule_url(self.schedule), 'method': 'PATCH', 'data': {'retention_time': 5}}
        instance_url = 'http://testserver' + reverse('instance-detail', args=(self.instance.uuid.hex,))
        backup_schedule_data = {
            'retention_time': 3,
            'backup_source': instance_url,
            'schedule': '*/5 * * * *',
            'maximal_number_of_backups': 3,
        }
        yield {'url': _backup_list_url(), 'method': 'POST', 'data': backup_schedule_data}

    # XXX: Current permissions tests helper does not work well with deletion, so we need to test deletion explicitly
    def test_staff_can_delete_schedule(self):
        self.client.force_authenticate(self.staff)

        url = _backup_schedule_url(self.schedule)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_admin_can_delete_schedule(self):
        self.client.force_authenticate(self.staff)

        url = _backup_schedule_url(self.schedule)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_owner_cannot_delete_schedule(self):
        self.client.force_authenticate(self.customer_owner)

        url = _backup_schedule_url(self.schedule)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_group_manager_cannot_delete_schedule(self):
        self.client.force_authenticate(self.project_group_manager)

        url = _backup_schedule_url(self.schedule)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
