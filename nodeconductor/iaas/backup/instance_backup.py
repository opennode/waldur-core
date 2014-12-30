from django.utils import six

from nodeconductor.backup.models import BackupStrategy
from nodeconductor.backup.exceptions import BackupStrategyExecutionError
from nodeconductor.iaas.backend import CloudBackendError
from nodeconductor.iaas.models import Instance


class InstanceBackupStrategy(BackupStrategy):

    @classmethod
    def get_model(cls):
        return Instance

    @classmethod
    def backup(cls, instance):
        try:
            backend = cls._get_backend(instance)
            backup_ids = backend.backup_instance(instance)
            return ','.join(backup_ids)
        except CloudBackendError as e:
            six.reraise(BackupStrategyExecutionError, e)

    @classmethod
    def restore(cls, instance, backup_ids):
        try:
            if backup_ids:
                backup_ids = backup_ids.split(',')
            backend = cls._get_backend(instance)
            vm = backend.restore_instance(instance, backup_ids)
            instance.backend_id = vm.id
            instance.save()
        except CloudBackendError as e:
            six.reraise(BackupStrategyExecutionError, e)

    @classmethod
    def delete(cls, instance, backup_ids):
        try:
            if backup_ids:
                backup_ids = backup_ids.split(',')
            backend = cls._get_backend(instance)
            backend.delete_instance_backup(instance, backup_ids)
        except CloudBackendError as e:
            six.reraise(BackupStrategyExecutionError, e)

    # Helpers
    @classmethod
    def _get_backend(cls, instance):
        return instance.cloud_project_membership.cloud.get_backend()
