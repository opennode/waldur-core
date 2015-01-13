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
    def backup(cls, instance):
        """
        Copy instance volumes and return new volumes ids and info about instance
        """
        try:
            backend = cls._get_backend(instance)
            cloned_system_volume_id, cloned_data_volume_id = backend.clone_volumes(
                membership=instance.cloud_project_membership,
                volume_ids=[instance.system_volume_id, instance.data_volume_id],
                prefix='Backup volume'
            )
        except CloudBackendError as e:
            six.reraise(BackupStrategyExecutionError, e)

        # populate backup metadata
        metadata = cls._get_instance_metadata(instance)
        metadata['system_volume_id'] = cloned_system_volume_id
        metadata['data_volume_id'] = cloned_data_volume_id

        return metadata

    @classmethod
    def deserialize_instance(cls, metadata, user_raw_input):
        user_input = {
            'hostname': user_raw_input.get('hostname'),
            'flavor': user_raw_input.get('flavor'),
        }
        # overwrite metadata attributes with user provided ones
        input_parameters = dict(metadata.items() + [u for u in user_input.items() if u[1] is not None])

        # import here to avoid circular dependency
        serializer = InstanceBackupRestorationSerializer(data=input_parameters)

        if serializer.is_valid():
            serializer.object.save()
            # all user_input should be json serializable
            user_input = {
                'flavor_uuid': serializer.object.flavor.uuid.hex,
            }
            # note that root/system volumes of a backup will be linked to the volumes belonging to a backup
            return serializer.object, user_input, None

        # if there were errors in input parameters
        errors = dict(serializer.errors)

        try:
            non_field_errors = errors.pop('non_field_errors')
            errors['detail'] = non_field_errors[0]
        except (KeyError, IndexError):
            pass

        return None, None, errors

    @classmethod
    def restore(cls, instance_uuid, user_input):
        """
        Create a new instance from the backup and user input. Input is expected to be previously validated.
        """
        instance = models.Instance.objects.get(uuid=instance_uuid)

        # create a copy of the volumes to be used by a new VM
        try:
            backend = cls._get_backend(instance)
            cloned_system_volume_id, cloned_data_volume_id = backend.clone_volumes(
                membership=instance.cloud_project_membership,
                volume_ids=[instance.system_volume_id, instance.data_volume_id],
                prefix='Restored volume'
            )
        except CloudBackendError as e:
            six.reraise(BackupStrategyExecutionError, e)

        # flavor is required for provisioning - it is filled in by serializer and is mandatory
        flavor = models.Flavor.objects.get(uuid=user_input['flavor_uuid'])

        tasks.schedule_provisioning.delay(
            instance.uuid.hex,
            backend_flavor_id=flavor.backend_id,
            system_volume_id=cloned_system_volume_id,
            data_volume_id=cloned_data_volume_id
        )

        return instance

    @classmethod
    def delete(cls, source, metadata):
        try:
            backend = cls._get_backend(source)
            backend.delete_volumes(
                membership=source.cloud_project_membership,
                volume_ids=[metadata['system_volume_id'], metadata['data_volume_id']]
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
            'hostname': instance.hostname,
            'template': instance.template.pk,
            'system_volume_id': instance.system_volume_id,
            'system_volume_size': instance.system_volume_size,
            'data_volume_id': instance.data_volume_id,
            'data_volume_size': instance.data_volume_size,
            'key_name': instance.key_name,
            'key_fingerprint': instance.key_fingerprint,
            'agreed_sla': instance.agreed_sla,
        }
        return metadata
