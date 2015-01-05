from django.utils import six

from nodeconductor.backup.models import BackupStrategy
from nodeconductor.backup.exceptions import BackupStrategyExecutionError
from nodeconductor.iaas import tasks
from nodeconductor.iaas.backend import CloudBackendError
from nodeconductor.iaas.models import Instance


class InstanceBackupStrategy(BackupStrategy):

    @classmethod
    def get_model(cls):
        return Instance

    @classmethod
    def backup(cls, instance):
        """
        Copy instance volumes and return new volumes ids and info about instance
        """
        try:
            backend = cls._get_backend(instance)
            copied_system_volume_id, copied_data_volume_id = backend.copy_volumes(
                membership=instance.cloud_project_membership,
                volume_ids=[instance.system_volume_id, instance.data_volume_id]
            )
        except CloudBackendError as e:
            six.reraise(BackupStrategyExecutionError, e)
        additional_data = cls._get_instance_addition_data(instance)
        additional_data['system_volume_id'] = copied_system_volume_id
        additional_data['data_volume_id'] = copied_data_volume_id
        return additional_data

    @classmethod
    def restore(cls, source, additional_data, key, flavor, hostname=None):
        """
        Create new instance from backup, key and flavor has to be defined, because old one could be deleted
        """
        try:
            backend = cls._get_backend(source)
            copied_system_volume_id, copied_data_volume_id = backend.copy_volumes(
                membership=source.cloud_project_membership,
                volume_ids=[additional_data.pop('system_volume_id'), additional_data.pop('data_volume_id')],
                prefix='Restored volume',
            )
        except CloudBackendError as e:
            six.reraise(BackupStrategyExecutionError, e)

        restored_instance = Instance(cloud_project_membership=source.cloud_project_membership)
        if hostname is not None:
            restored_instance.hostname = hostname
            del additional_data['hostname']

        for k, v in additional_data.iteritems():
            setattr(restored_instance, k, v)

        restored_instance.cores = flavor.cores
        restored_instance.ram = flavor.ram
        restored_instance.system_volume_size = flavor.disk

        restored_instance.key_name = key.name
        restored_instance.key_fingerprint = key.fingerprint

        restored_instance.save()

        tasks.schedule_provisioning.delay(
            restored_instance.uuid.hex,
            backend_flavor_id=flavor.backend_id,
            system_volume_id=copied_system_volume_id,
            data_volume_id=copied_data_volume_id
        )

        return restored_instance

    @classmethod
    def delete(cls, source, additional_data):
        try:
            backend = cls._get_backend(source)
            backend.delete_volumes(
                membership=source.cloud_project_membership,
                volume_ids=[additional_data['system_volume_id'], additional_data['data_volume_id']]
            )
        except CloudBackendError as e:
            six.reraise(BackupStrategyExecutionError, e)

    # Helpers
    @classmethod
    def _get_backend(cls, instance):
        return instance.cloud_project_membership.cloud.get_backend()

    @classmethod
    def _get_instance_addition_data(cls, instance):
        """
        Return additional instance information, that have to be stored with backup
        """
        return {
            'hostname': instance.hostname,
            'template_id': instance.template_id,
            'external_ips': instance.external_ips,
            'internal_ips': instance.internal_ips,
            'agreed_sla': instance.agreed_sla,
            'system_volume_size': instance.system_volume_size,
            'data_volume_size': instance.data_volume_size,
        }
