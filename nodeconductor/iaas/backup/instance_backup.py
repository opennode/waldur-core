from nodeconductor.backup.models import BackupStrategy
from nodeconductor.iaas.models import Instance


class InstanceBackupStrategy(BackupStrategy):

    @classmethod
    def get_model(cls):
        return Instance

    @classmethod
    def backup(cls, instance):
        backend = cls._get_backend(instance)
        backup_ids = backend.backup_instance(instance)
        return ','.join(backup_ids)

    @classmethod
    def restore(cls, instance, backup_ids):
        if backup_ids:
            backup_ids = backup_ids.split(',')
        backend = cls._get_backend(instance)
        vm = backend.restore_instance(instance, backup_ids)
        instance.backend_id = vm.id
        instance.save()

    @classmethod
    def delete(cls, instance, additional_data=None):
        backend = cls._get_backend(instance)
        backend.delete_instance(instance)

    # Helpers
    @classmethod
    def _get_backend(cls, instance):
        return instance.flavor.cloud.get_backend()
