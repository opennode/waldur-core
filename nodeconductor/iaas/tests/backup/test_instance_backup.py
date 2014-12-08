from __future__ import unicode_literals

from mock import Mock

from django.utils import unittest

from nodeconductor.iaas.backup.instance_backup import InstanceBackupStrategy


class InstanceBackupStrategyTestCase(unittest.TestCase):

    def setUp(self):
        self.backup_ids = ['a52ef740-8dfa-4a26-87d5-3b5bb095681d', 'c695e654-d6a4-4202-b1b9-eb1e66aa43a5']
        self.additional_data = ','.join(self.backup_ids)
        self.instance = Mock()
        self.restored_vm = Mock()
        self.restored_vm.id = 2

        self.mocked_backed = Mock()
        InstanceBackupStrategy._get_backend = Mock(return_value=self.mocked_backed)
        self.mocked_backed.backup_instance = Mock(return_value=self.backup_ids)
        self.mocked_backed.restore_instance = Mock(return_value=self.restored_vm)

    def test_strategy_backup_method_calls_backend_backup_instance_method(self):
        InstanceBackupStrategy.backup(self.instance)
        self.mocked_backed.backup_instance.assert_called_once_with(self.instance)

    def test_strategy_backup_method_returns_backups_ids_as_string(self):
        result = InstanceBackupStrategy.backup(self.instance)
        expected = ','.join(self.backup_ids)
        self.assertEqual(result, expected)

    def test_strategy_restore_method_calls_backend_restore_instance_method(self):
        InstanceBackupStrategy.restore(self.instance, self.additional_data)
        self.mocked_backed.restore_instance.assert_called_once_with(self.instance, self.backup_ids)

    def test_strategy_restore_method_replace_instance_backend_id(self):
        InstanceBackupStrategy.restore(self.instance, self.additional_data)
        self.assertEqual(self.instance.backend_id, self.restored_vm.id)
        self.instance.save.assert_called_once_with()

    @unittest.skip('FIXME')
    def test_strategy_delete_method_calls_backend_delete_instance_method(self):
        InstanceBackupStrategy.delete(self.instance, self.additional_data)
        self.mocked_backed.delete_instance.assert_called_once_with(self.instance)
