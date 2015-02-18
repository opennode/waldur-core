from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.backup import models
from nodeconductor.backup.tests import factories
from nodeconductor.core.tests import helpers
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.iaas.tests import factories as iaas_factories


def _backup_list_url():
    return 'http://testserver' + reverse('backup-list')


def _backup_schedule_url(schedule, action=None):
    url = 'http://testserver' + reverse('backupschedule-detail', args=(str(schedule.uuid), ))
    return url if action is None else url + action + '/'


def _backup_schedule_list_url():
    return 'http://testserver' + reverse('backupschedule-list')


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
        return [self.staff, self.project_admin, self.project_group_manager, self.customer_owner]

    def get_users_without_permissions(self, url, method):
        return [self.regular_user]

    def get_urls_configs(self):
        schedule = factories.BackupScheduleFactory(backup_source=self.instance)
        yield {'url': _backup_schedule_url(schedule), 'method': 'GET'}
        yield {'url': _backup_schedule_url(schedule, action='deactivate'), 'method': 'POST'}
        yield {'url': _backup_schedule_url(schedule, action='activate'), 'method': 'POST'}
        yield {'url': _backup_schedule_url(schedule), 'method': 'PUT'}
        yield {'url': _backup_schedule_url(schedule), 'method': 'DELETE'}
        instance_url = 'http://testserver' + reverse('instance-detail', args=(self.instance.uuid.hex,))
        backup_schedule_data = {
            'retention_time': 3,
            'backup_source': instance_url,
            'schedule': '*/5 * * * *',
            'maximal_number_of_backups': 3,
        }
        yield {'url': _backup_list_url(), 'method': 'POST', 'data': backup_schedule_data}
