from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.backup import models
from nodeconductor.backup.tests import factories
from nodeconductor.core.tests import helpers
from nodeconductor.iaas.models import Instance
from nodeconductor.iaas.tests import factories as iaas_factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


def _backup_url(backup, action=None):
    url = 'http://testserver' + reverse('backup-detail', args=(str(backup.uuid), ))
    return url if action is None else url + action + '/'


def _backup_list_url():
    return 'http://testserver' + reverse('backup-list')


def _instance_url(instance):
    return 'http://testserver' + reverse('instance-detail', kwargs={'uuid': instance.uuid})


class BackupUsageTest(test.APITransactionTestCase):

    def setUp(self):
        self.user = structure_factories.UserFactory.create(is_staff=True, is_superuser=True)
        self.client.force_authenticate(user=self.user)

    def test_backup_manually_create(self):
        # success:
        backupable = iaas_factories.InstanceFactory(state=Instance.States.OFFLINE)
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

    def test_user_cannot_backup_unstable_instance(self):
        backupable = iaas_factories.InstanceFactory(state=Instance.States.RESIZING)
        backup_data = {
            'backup_source': iaas_factories.InstanceFactory.get_url(backupable),
        }
        url = _backup_list_url()
        response = self.client.post(url, data=backup_data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['detail'], 'Backup source should be in stable state.')

    def test_backup_restore(self):
        backup = factories.BackupFactory()
        url = _backup_url(backup, action='restore')
        user_input = {
            'flavor': iaas_factories.FlavorFactory.get_url(iaas_factories.FlavorFactory(
                cloud=backup.backup_source.cloud_project_membership.cloud
            ))
        }
        response = self.client.post(url, data=user_input)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(models.Backup.objects.get(pk=backup.pk).state, models.Backup.States.RESTORING)

    def test_backup_delete(self):
        backup = factories.BackupFactory()
        url = _backup_url(backup, action='delete')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(models.Backup.objects.get(pk=backup.pk).state, models.Backup.States.DELETING)


class BackupListPermissionsTest(helpers.ListPermissionsTest):

    def get_url(self):
        return _backup_list_url()

    def get_users_and_expected_results(self):
        models.Backup.objects.all().delete()
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
        super(BackupPermissionsTest, self).setUp()
        # objects
        self.customer = structure_factories.CustomerFactory()
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project_group = structure_factories.ProjectGroupFactory(customer=self.customer)
        self.project_group.projects.add(self.project)
        self.cloud = iaas_factories.CloudFactory(customer=self.customer)
        self.cpm = iaas_factories.CloudProjectMembershipFactory(cloud=self.cloud, project=self.project)
        self.instance = iaas_factories.InstanceFactory(cloud_project_membership=self.cpm)
        self.backup = factories.BackupFactory(backup_source=self.instance)
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
            return [self.staff, self.project_admin, self.customer_owner]

    def get_users_without_permissions(self, url, method):
        if method == 'GET':
            return [self.regular_user]
        else:
            return [self.project_group_manager]

    def get_urls_configs(self):
        yield {'url': _backup_url(self.backup), 'method': 'GET'}
        yield {'url': _backup_url(self.backup, action='restore'), 'method': 'POST'}
        instance_url = 'http://testserver' + reverse('instance-detail', args=(self.instance.uuid.hex,))
        yield {'url': _backup_list_url(), 'method': 'POST',
               'data': {'backup_source': instance_url}}
        yield {'url': _backup_url(self.backup, action='delete'), 'method': 'POST'}


class BackupSourceFilterTest(test.APITransactionTestCase):

    def test_filter_backup_by_scope(self):
        user = structure_factories.UserFactory.create(is_staff=True)

        instance1 = iaas_factories.InstanceFactory()
        backup1 = factories.BackupFactory(backup_source=instance1)
        backup2 = factories.BackupFactory(backup_source=instance1)

        instance2 = iaas_factories.InstanceFactory()
        backup3 = factories.BackupFactory(backup_source=instance2)

        self.client.force_authenticate(user=user)
        response = self.client.get(_backup_list_url())
        self.assertEqual(3, len(response.data))

        response = self.client.get(_backup_list_url(), data={'backup_source': _instance_url(instance1)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(2, len(response.data))
        self.assertEqual(_instance_url(instance1), response.data[0]['backup_source'])
