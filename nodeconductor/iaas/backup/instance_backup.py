from django.utils import six

from nodeconductor.backup.models import BackupStrategy
from nodeconductor.backup.exceptions import BackupStrategyExecutionError
from nodeconductor.iaas import tasks
from nodeconductor.iaas.backend import CloudBackendError
from nodeconductor.iaas import models
from nodeconductor.iaas.backup.serializers import InstanceBackupRestorationSerializer


class InstanceBackupStrategy(BackupStrategy):

    @classmethod
    def get_model(cls):
        return models.Instance

    @classmethod
    def _is_storage_resource_available(cls, instance):
        membership = instance.cloud_project_membership

        storage_delta = {
            'storage': instance.system_volume_size + instance.data_volume_size
        }
        quota_errors = membership.validate_quota_change(storage_delta)

        return not bool(quota_errors)

    @classmethod
    def backup(cls, instance):
        """
        Snapshot instance volumes and return snapshot ids and info about instance
        """
        if not cls._is_storage_resource_available(instance):
            raise BackupStrategyExecutionError('No space for instance %s backup' % instance.uuid.hex)
        try:
            backend = cls._get_backend(instance)
            snapshots = backend.create_snapshots(
                membership=instance.cloud_project_membership,
                volume_ids=[instance.system_volume_id, instance.data_volume_id],
                prefix='Instance %s backup: ' % instance.uuid,
            )
            system_volume_snapshot_id, data_volume_snapshot_id = snapshots
        except CloudBackendError as e:
            six.reraise(BackupStrategyExecutionError, e)

        # populate backup metadata
        metadata = cls._get_instance_metadata(instance)
        metadata['system_snapshot_id'] = system_volume_snapshot_id
        metadata['data_snapshot_id'] = data_volume_snapshot_id
        metadata['system_snapshot_size'] = instance.system_volume_size
        metadata['data_snapshot_size'] = instance.data_volume_size

        return metadata

    @classmethod
    def deserialize_instance(cls, metadata, user_raw_input):
        user_input = {
            'name': user_raw_input.get('name'),
            'flavor': user_raw_input.get('flavor'),
        }
        # overwrite metadata attributes with user provided ones
        input_parameters = dict(metadata.items() + [u for u in user_input.items() if u[1] is not None])
        # special treatment for volume sizes -- they will be created equal to snapshot sizes
        try:
            input_parameters['system_volume_size'] = metadata['system_snapshot_size']
            input_parameters['data_volume_size'] = metadata['data_snapshot_size']
        except (KeyError, IndexError):
            return None, None, None, {'detail': 'Missing system_snapshot_size or data_snapshot_size in metadata'}

        # import here to avoid circular dependency
        serializer = InstanceBackupRestorationSerializer(data=input_parameters)

        if serializer.is_valid():
            try:
                system_volume_snapshot_id = metadata['system_snapshot_id']
                data_volume_snapshot_id = metadata['data_snapshot_id']
            except (KeyError, IndexError):
                return None, None, None, {'detail': 'Missing system_snapshot_id or data_snapshot_id in metadata'}
            flavor = serializer.validated_data['flavor']
            obj = serializer.save()
            # all user_input should be json serializable
            user_input = {
                'flavor_uuid': flavor.uuid.hex,
            }
            # note that root/system volumes of a backup will be linked to the volumes belonging to a backup
            return obj, user_input, [system_volume_snapshot_id, data_volume_snapshot_id], None

        # if there were errors in input parameters
        errors = dict(serializer.errors)

        try:
            non_field_errors = errors.pop('non_field_errors')
            errors['detail'] = non_field_errors[0]
        except (KeyError, IndexError):
            pass

        return None, None, None, errors

    @classmethod
    def restore(cls, instance_uuid, user_input, snapshot_ids):
        """
        Create a new instance from the backup and user input. Input is expected to be previously validated.
        """
        instance = models.Instance.objects.get(uuid=instance_uuid)

        # create a copy of the volumes to be used by a new VM
        try:
            backend = cls._get_backend(instance)
            cloned_volumes_ids = backend.promote_snapshots_to_volumes(
                membership=instance.cloud_project_membership,
                snapshot_ids=snapshot_ids,
                prefix='Restored volume'
            )
        except CloudBackendError as e:
            six.reraise(BackupStrategyExecutionError, e)

        # flavor is required for provisioning - it is filled in by serializer and is mandatory
        flavor = models.Flavor.objects.get(uuid=user_input['flavor_uuid'])

        tasks.provision_instance.delay(
            instance.uuid.hex,
            backend_flavor_id=flavor.backend_id,
            system_volume_id=cloned_volumes_ids[0],
            data_volume_id=cloned_volumes_ids[1]
        )

    @classmethod
    def delete(cls, source, metadata):
        try:
            backend = cls._get_backend(source)
            backend.delete_snapshots(
                membership=source.cloud_project_membership,
                snapshot_ids=[metadata['system_snapshot_id'], metadata['data_snapshot_id']],
            )
        except CloudBackendError as e:
            six.reraise(BackupStrategyExecutionError, e)

    # Helpers
    @classmethod
    def _get_backend(cls, instance):
        return instance.cloud_project_membership.cloud.get_backend()

    @classmethod
    def _get_instance_metadata(cls, instance):
        # populate backup metadata
        metadata = {
            'cloud_project_membership': instance.cloud_project_membership.pk,
            'name': instance.name,
            'template': instance.template.pk,
            'system_volume_id': instance.system_volume_id,
            'system_volume_size': instance.system_volume_size,
            'data_volume_id': instance.data_volume_id,
            'data_volume_size': instance.data_volume_size,
            'key_name': instance.key_name,
            'key_fingerprint': instance.key_fingerprint,
            'agreed_sla': instance.agreed_sla,
            'user_data': instance.user_data,
            'type': instance.type,
        }
        return metadata
