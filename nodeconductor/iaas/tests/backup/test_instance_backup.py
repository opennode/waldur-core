from __future__ import unicode_literals
from decimal import Decimal

from django.db.models import ProtectedError
from django.test import TransactionTestCase
from mock import Mock
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from nodeconductor.backup.models import Backup, BackupSchedule
from nodeconductor.backup.exceptions import BackupStrategyExecutionError
from nodeconductor.backup.tests import factories as backup_factories
from nodeconductor.iaas.backup.instance_backup import InstanceBackupStrategy
from nodeconductor.iaas.models import Instance
from nodeconductor.iaas.tests import factories
from nodeconductor.structure.tests import factories as structure_factories


class InstanceBackupStrategyTestCase(TransactionTestCase):

    def setUp(self):
        self.system_volume_snapshot_id = '350b81e1-f991-401c-99b1-ebccc5a517a6'
        self.data_volume_snapshot_id = 'dba9b361-277c-46b2-99ca-1136b3eba6ed'

        self.template = factories.TemplateFactory()
        factories.TemplateLicenseFactory(templates=(self.template,))

        self.instance = factories.InstanceFactory(template=self.template)
        self.backup = backup_factories.BackupFactory(
            backup_source=self.instance,
            metadata={
                'system_snapshot_id': self.system_volume_snapshot_id,
                'data_snapshot_id': self.data_volume_snapshot_id,
            }
        )
        self.flavor = factories.FlavorFactory(cloud=self.backup.backup_source.cloud_project_membership.cloud)
        self.user_input = {
            'name': 'new_name',
            'flavor': factories.FlavorFactory.get_url(self.flavor),
        }
        self.metadata = InstanceBackupStrategy._get_instance_metadata(self.instance)
        self.metadata['system_snapshot_id'] = self.system_volume_snapshot_id
        self.metadata['data_snapshot_id'] = self.data_volume_snapshot_id
        self.agreed_sla = Decimal('99.9')
        self.metadata['agreed_sla'] = self.agreed_sla

        self.mocked_backed = Mock()
        InstanceBackupStrategy._get_backend = Mock(return_value=self.mocked_backed)
        self.mocked_backed.create_snapshots = Mock(
            return_value=([self.system_volume_snapshot_id, self.data_volume_snapshot_id]))

        self.mocked_backed.promote_snapshots_to_volumes = Mock(
            return_value=([self.system_volume_snapshot_id, self.data_volume_snapshot_id]))

    def test_strategy_backup_method_calls_backend_backup_instance_method(self):
        InstanceBackupStrategy.backup(self.instance)
        self.mocked_backed.create_snapshots.assert_called_once_with(
            membership=self.instance.cloud_project_membership,
            volume_ids=[self.instance.system_volume_id, self.instance.data_volume_id],
            prefix='Instance %s backup: ' % self.instance.uuid,
        )

    def test_strategy_backup_method_returns_backups_ids_as_string(self):
        result = InstanceBackupStrategy.backup(self.instance)
        expected = InstanceBackupStrategy._get_instance_metadata(self.instance)
        expected['system_snapshot_id'] = self.system_volume_snapshot_id
        expected['data_snapshot_id'] = self.data_volume_snapshot_id
        expected['system_snapshot_size'] = self.instance.system_volume_size
        expected['data_snapshot_size'] = self.instance.data_volume_size

        self.maxDiff = None
        self.assertEqual(result, expected)

    def test_strategy_restore_method_calls_backend_restore_instance_method(self):
        new_instance, user_input, snapshot_ids, errors = InstanceBackupStrategy.\
            deserialize_instance(self.backup.metadata, self.user_input)
        self.assertIsNone(errors, 'Deserialization errors: %s' % errors)
        InstanceBackupStrategy.restore(new_instance.uuid, user_input, snapshot_ids)
        self.mocked_backed.promote_snapshots_to_volumes.assert_called_once_with(
            membership=self.instance.cloud_project_membership,
            snapshot_ids=[self.system_volume_snapshot_id, self.data_volume_snapshot_id],
            prefix='Restored volume',
        )

    def test_strategy_restore_method_creates_new_instance(self):
        new_instance, user_input, snapshot_ids, errors = InstanceBackupStrategy.\
            deserialize_instance(self.backup.metadata, self.user_input)
        self.assertIsNone(errors, 'Deserialization errors: %s' % errors)
        self.assertEqual(new_instance.name, 'new_name')
        self.assertNotEqual(new_instance.id, self.instance.id)
        self.assertEqual(new_instance.agreed_sla, self.agreed_sla)

    def test_strategy_delete_method_calls_backend_delete_instance_method(self):
        InstanceBackupStrategy.delete(self.instance, self.metadata)
        self.mocked_backed.delete_snapshots.assert_called_once_with(
            membership=self.instance.cloud_project_membership,
            snapshot_ids=[self.system_volume_snapshot_id, self.data_volume_snapshot_id],
        )

    def test_strategy_restore_method_fails_if_where_is_no_space_on_resource_storage(self):
        self.instance.cloud_project_membership.set_quota_limit('storage', self.instance.system_volume_size)
        self.assertRaises(BackupStrategyExecutionError, lambda: InstanceBackupStrategy.backup(self.instance))

    def test_strategy_deserialize_instance_method_return_errors_if_ram_quota_exceeded(self):
        self.instance.cloud_project_membership.set_quota_limit('ram', self.instance.ram)
        _, _, _, errors = InstanceBackupStrategy.deserialize_instance(self.backup.metadata, self.user_input)
        self.assertTrue(errors)

    def test_strategy_deserialize_instance_method_return_errors_if_vcpu_quota_exceeded(self):
        self.instance.cloud_project_membership.set_quota_limit(
            'vcpu', self.instance.cloud_project_membership.quotas.get(name='vcpu').usage)
        _, _, _, errors = InstanceBackupStrategy.deserialize_instance(self.backup.metadata, self.user_input)
        self.assertTrue(errors)

    def test_strategy_deserialize_instance_method_return_errors_if_storage_quota_exceeded(self):
        self.instance.cloud_project_membership.set_quota_limit('storage', self.instance.data_volume_size)
        _, _, _, errors = InstanceBackupStrategy.deserialize_instance(self.backup.metadata, self.user_input)
        self.assertTrue(errors)


class InstanceDeletionTestCase(APITransactionTestCase):

    def test_cannot_delete_instance_with_connected_backup(self):
        instance = factories.InstanceFactory(state=Instance.States.OFFLINE)
        Backup.objects.create(
            backup_source=instance,
        )

        with self.assertRaises(ProtectedError):
            instance.delete()

        self.client.force_authenticate(structure_factories.UserFactory(is_staff=True))
        response = self.client.delete(factories.InstanceFactory.get_url(instance))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_can_initiate_deletion_of_instance_with_connected_backup_schedule(self):
        instance = factories.InstanceFactory(state=Instance.States.OFFLINE)
        BackupSchedule.objects.create(
            backup_source=instance,
            schedule="* * * * *",
            retention_time=1,
            maximal_number_of_backups=2,
        )

        self.client.force_authenticate(structure_factories.UserFactory(is_staff=True))
        response = self.client.delete(factories.InstanceFactory.get_url(instance))
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
