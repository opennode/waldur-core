from __future__ import unicode_literals

from django.db.models import ProtectedError
from django.test import TransactionTestCase
from mock import Mock
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from nodeconductor.backup.models import Backup
from nodeconductor.backup.exceptions import BackupStrategyExecutionError
from nodeconductor.backup.tests import factories as backup_factories
from nodeconductor.iaas.backup.instance_backup import InstanceBackupStrategy
from nodeconductor.iaas.tests import factories
from nodeconductor.structure.tests import factories as structure_factories


class InstanceBackupStrategyTestCase(TransactionTestCase):

    def setUp(self):
        self.copied_system_volume_id = '350b81e1-f991-401c-99b1-ebccc5a517a6'
        self.copied_data_volume_id = 'dba9b361-277c-46b2-99ca-1136b3eba6ed'
        self.snapshot_ids = ['2b0282c8-21b6-4a86-a3d4-e731c5482e6e', '2b0282c8-21b6-4a86-l3d4-q732r1321e6e']

        self.template = factories.TemplateFactory()
        factories.TemplateLicenseFactory(templates=(self.template,))

        self.instance = factories.InstanceFactory(template=self.template)
        factories.ResourceQuotaFactory(
            cloud_project_membership=self.instance.cloud_project_membership, storage=10 * 1024 * 1024)
        self.backup = backup_factories.BackupFactory(
            backup_source=self.instance,
            metadata={
                'system_volume_id': self.copied_system_volume_id,
                'data_volume_id': self.copied_data_volume_id,
            }
        )
        self.flavor = factories.FlavorFactory(cloud=self.backup.backup_source.cloud_project_membership.cloud)
        self.user_input = {
            'hostname': 'new_hostname',
            'flavor': factories.FlavorFactory.get_url(self.flavor),
        }
        self.metadata = InstanceBackupStrategy._get_instance_metadata(self.instance)
        self.metadata['system_volume_id'] = self.copied_system_volume_id
        self.metadata['data_volume_id'] = self.copied_data_volume_id
        self.metadata['snapshot_ids'] = self.snapshot_ids

        self.mocked_backed = Mock()
        InstanceBackupStrategy._get_backend = Mock(return_value=self.mocked_backed)
        self.mocked_backed.clone_volumes = Mock(
            return_value=([self.copied_system_volume_id, self.copied_data_volume_id], self.snapshot_ids))

    def test_strategy_backup_method_calls_backend_backup_instance_method(self):
        InstanceBackupStrategy.backup(self.instance)
        self.mocked_backed.clone_volumes.assert_called_once_with(
            membership=self.instance.cloud_project_membership,
            volume_ids=[self.instance.system_volume_id, self.instance.data_volume_id],
            prefix='Backup volume',
        )

    def test_strategy_backup_method_returns_backups_ids_as_string(self):
        result = InstanceBackupStrategy.backup(self.instance)
        expected = InstanceBackupStrategy._get_instance_metadata(self.instance)
        expected['system_volume_id'] = self.copied_system_volume_id
        expected['data_volume_id'] = self.copied_data_volume_id
        expected['snapshot_ids'] = self.snapshot_ids
        self.assertEqual(result, expected)

    def test_strategy_restore_method_calls_backend_restore_instance_method(self):
        new_instance, user_input, errors = InstanceBackupStrategy.deserialize_instance(self.backup.metadata,
                                                                                       self.user_input)
        self.assertIsNone(errors, 'Deserialization errors: %s' % errors)
        InstanceBackupStrategy.restore(new_instance.uuid, user_input)
        self.mocked_backed.clone_volumes.assert_called_once_with(
            membership=self.instance.cloud_project_membership,
            volume_ids=[self.copied_system_volume_id, self.copied_data_volume_id],
            prefix='Restored volume',
        )

    def test_strategy_restore_method_creates_new_instance(self):
        new_instance, user_input, errors = InstanceBackupStrategy.deserialize_instance(self.backup.metadata,
                                                                                       self.user_input)
        self.assertIsNone(errors, 'Deserialization errors: %s' % errors)
        self.assertEqual(new_instance.hostname, 'new_hostname')
        self.assertNotEqual(new_instance.id, self.instance.id)

    def test_strategy_delete_method_calls_backend_delete_instance_method(self):
        InstanceBackupStrategy.delete(self.instance, self.metadata)
        self.mocked_backed.delete_volumes_with_snapshots.assert_called_once_with(
            membership=self.instance.cloud_project_membership,
            volume_ids=[self.copied_system_volume_id, self.copied_data_volume_id],
            snapshot_ids=self.snapshot_ids,
        )

    def test_strategy_restore_method_fails_if_where_is_no_space_on_resource_storage(self):
        factories.ResourceQuotaUsageFactory(
            cloud_project_membership=self.instance.cloud_project_membership, storage=10 * 1024 * 1024)
        self.assertRaises(BackupStrategyExecutionError, lambda: InstanceBackupStrategy.backup(self.instance))


class InstanceDeletionTestCase(APITransactionTestCase):

    def test_cannot_delete_instance_with_connected_backup(self):
        instance = factories.InstanceFactory()
        Backup.objects.create(
            backup_source=instance,
        )

        with self.assertRaises(ProtectedError):
            instance.delete()

        self.client.force_authenticate(structure_factories.UserFactory(is_staff=True))
        response = self.client.delete(factories.InstanceFactory.get_url(instance))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
