from __future__ import unicode_literals

from mock import Mock

from django.utils import unittest

from nodeconductor.iaas.backup.instance_backup import InstanceBackupStrategy
from nodeconductor.iaas.tests import factories


class InstanceBackupStrategyTestCase(unittest.TestCase):

    def setUp(self):
        self.instance = factories.InstanceFactory()
        self.flavor = factories.FlavorFactory()
        self.key = factories.SshPublicKeyFactory()
        self.copied_system_volume_id = '350b81e1-f991-401c-99b1-ebccc5a517a6'
        self.copied_data_volume_id = 'dba9b361-277c-46b2-99ca-1136b3eba6ed'
        self.additional_data = InstanceBackupStrategy._get_instance_addition_data(self.instance)
        self.additional_data['system_volume_id'] = self.copied_system_volume_id
        self.additional_data['data_volume_id'] = self.copied_data_volume_id

        self.mocked_backed = Mock()
        InstanceBackupStrategy._get_backend = Mock(return_value=self.mocked_backed)
        self.mocked_backed.copy_volumes = Mock(return_value=[self.copied_system_volume_id, self.copied_data_volume_id])

    def test_strategy_backup_method_calls_backend_backup_instance_method(self):
        InstanceBackupStrategy.backup(self.instance)
        self.mocked_backed.copy_volumes.assert_called_once_with(
            membership=self.instance.cloud_project_membership,
            volume_ids=[self.instance.system_volume_id, self.instance.data_volume_id]
        )

    def test_strategy_backup_method_returns_backups_ids_as_string(self):
        result = InstanceBackupStrategy.backup(self.instance)
        expected = InstanceBackupStrategy._get_instance_addition_data(self.instance)
        expected['system_volume_id'] = self.copied_system_volume_id
        expected['data_volume_id'] = self.copied_data_volume_id
        self.assertEqual(result, expected)

    def test_strategy_restore_method_calls_backend_restore_instance_method(self):
        InstanceBackupStrategy.restore(self.instance, self.additional_data, self.key, self.flavor, 'new_hostname')
        self.mocked_backed.copy_volumes.assert_called_once_with(
            membership=self.instance.cloud_project_membership,
            volume_ids=[self.copied_system_volume_id, self.copied_data_volume_id],
            prefix='Restored volume',
        )

    def test_strategy_restore_method_creates_new_instance(self):
        new_instance = InstanceBackupStrategy.restore(
            self.instance, self.additional_data, self.key, self.flavor, 'new_hostname')
        self.assertEqual(new_instance.hostname, 'new_hostname')
        self.assertNotEqual(new_instance.id, self.instance.id)

    def test_strategy_delete_method_calls_backend_delete_instance_method(self):
        InstanceBackupStrategy.delete(self.instance, self.additional_data)
        self.mocked_backed.delete_volumes.assert_called_once_with(
            membership=self.instance.cloud_project_membership,
            volume_ids=[self.copied_system_volume_id, self.copied_data_volume_id],
        )
