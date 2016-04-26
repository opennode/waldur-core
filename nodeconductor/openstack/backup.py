import logging

from django.utils import six, timezone

from nodeconductor.core.tasks import send_task
from nodeconductor.structure import ServiceBackendError


logger = logging.getLogger(__name__)


class BackupError(Exception):
    pass


class BackupScheduleBackend(object):

    def __init__(self, schedule):
        self.schedule = schedule

    def check_instance_state(self):
        """
        Instance should be stable state.
        """
        instance = self.schedule.instance
        if instance.state not in instance.States.STABLE_STATES:
            logger.warning('Cannot execute backup schedule for %s in state %s.' % (instance, instance.state))
            return False

        return True

    def create_backup(self):
        """
        Creates new backup based on schedule and starts backup process
        """
        if not self.check_instance_state():
            return

        kept_until = timezone.now() + \
            timezone.timedelta(days=self.schedule.retention_time) if self.schedule.retention_time else None
        backup = self.schedule.backups.create(
            instance=self.schedule.instance, kept_until=kept_until, description='scheduled backup')
        backend = backup.get_backend()
        backend.start_backup()
        return backup

    def delete_extra_backups(self):
        """
        Deletes oldest existing backups if maximal_number_of_backups was reached
        """
        states = self.schedule.backups.model.States
        exclude_states = (states.DELETING, states.DELETED, states.ERRED)
        backups_count = self.schedule.backups.exclude(state__in=exclude_states).count()
        extra_backups_count = backups_count - self.schedule.maximal_number_of_backups
        if extra_backups_count > 0:
            for backup in self.schedule.backups.order_by('created_at')[:extra_backups_count]:
                backend = backup.get_backend()
                backend.start_deletion()

    def execute(self):
        """
        Creates new backup, deletes existing if maximal_number_of_backups was
        reached, calculates new next_trigger_at time.
        """
        self.create_backup()
        self.delete_extra_backups()
        self.schedule.update_next_trigger_at()
        self.schedule.save()


class BackupBackend(object):

    def __init__(self, backup):
        self.backup = backup

    def start_backup(self):
        self.backup.starting_backup()
        self.backup.save(update_fields=['state'])
        send_task('openstack', 'backup_start_create')(self.backup.uuid.hex)

    def start_deletion(self):
        self.backup.starting_deletion()
        self.backup.save(update_fields=['state'])
        send_task('openstack', 'backup_start_delete')(self.backup.uuid.hex)

    def start_restoration(self, instance_uuid, user_input, snapshot_ids):
        self.backup.starting_restoration()
        self.backup.save(update_fields=['state'])
        send_task('openstack', 'backup_start_restore')(
            self.backup.uuid.hex, instance_uuid, user_input, snapshot_ids)

    def get_metadata(self):
        # populate backup metadata
        instance = self.backup.instance
        metadata = {
            'name': instance.name,
            'service_project_link': instance.service_project_link.pk,
            'system_volume_id': instance.system_volume_id,
            'system_volume_size': instance.system_volume_size,
            'data_volume_id': instance.data_volume_id,
            'data_volume_size': instance.data_volume_size,
            'min_ram': instance.min_ram,
            'min_disk': instance.min_disk,
            'key_name': instance.key_name,
            'key_fingerprint': instance.key_fingerprint,
            'user_data': instance.user_data,
            'flavor_name': instance.flavor_name,
            'image_name': instance.image_name,
            'tags': [tag.name for tag in instance.tags.all()],
        }
        return metadata

    def create(self):
        instance = self.backup.instance
        spl = instance.service_project_link
        quota_errors = spl.validate_quota_change({
            'storage': instance.system_volume_size + instance.data_volume_size})

        if quota_errors:
            raise BackupError('No space for instance %s backup' % instance.uuid.hex)

        try:
            backend = instance.get_backend()
            snapshots = backend.create_snapshots(
                service_project_link=spl,
                volume_ids=[instance.system_volume_id, instance.data_volume_id],
                prefix='Instance %s backup: ' % instance.uuid,
            )
            system_volume_snapshot_id, data_volume_snapshot_id = snapshots
        except ServiceBackendError as e:
            six.reraise(BackupError, e)

        # populate backup metadata
        metadata = self.get_metadata()
        metadata['system_snapshot_id'] = system_volume_snapshot_id
        metadata['data_snapshot_id'] = data_volume_snapshot_id
        metadata['system_snapshot_size'] = instance.system_volume_size
        metadata['data_snapshot_size'] = instance.data_volume_size

        return metadata

    def delete(self):
        instance = self.backup.instance
        metadata = self.backup.metadata
        try:
            backend = instance.get_backend()
            backend.delete_snapshots(
                service_project_link=instance.service_project_link,
                snapshot_ids=[metadata['system_snapshot_id'], metadata['data_snapshot_id']],
            )
        except ServiceBackendError as e:
            six.reraise(BackupError, e)

    def restore(self, instance_uuid, user_input, snapshot_ids):
        instance = self.backup.instance.__class__.objects.get(uuid=instance_uuid)
        backend = instance.get_backend()

        # restore tags
        tags = self.backup.metadata.get('tags')
        if tags and isinstance(tags, list):
            instance.tags.add(*tags)

        # create a copy of the volumes to be used by a new VM
        try:
            cloned_volumes_ids = backend.promote_snapshots_to_volumes(
                service_project_link=instance.service_project_link,
                snapshot_ids=snapshot_ids,
                prefix='Restored volume'
            )
        except ServiceBackendError as e:
            six.reraise(BackupError, e)

        from nodeconductor.openstack.models import Flavor

        flavor = Flavor.objects.get(uuid=user_input['flavor_uuid'])

        backend.provision(
            instance,
            flavor=flavor,
            system_volume_id=cloned_volumes_ids[0],
            data_volume_id=cloned_volumes_ids[1],
            skip_external_ip_assignment=True)

    def deserialize(self, user_raw_input):
        metadata = self.backup.metadata
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
            return None, None, None, 'Missing system_snapshot_size or data_snapshot_size in metadata'

        # import here to avoid circular dependency
        from nodeconductor.openstack.serializers import BackupRestorationSerializer
        serializer = BackupRestorationSerializer(data=input_parameters)

        if serializer.is_valid():
            try:
                system_volume_snapshot_id = metadata['system_snapshot_id']
                data_volume_snapshot_id = metadata['data_snapshot_id']
            except (KeyError, IndexError):
                return None, None, None, 'Missing system_snapshot_id or data_snapshot_id in metadata'

            # all user_input should be json serializable
            user_input = {'flavor_uuid': serializer.validated_data.pop('flavor').uuid.hex}
            instance = serializer.save()
            # note that root/system volumes of a backup will be linked to the volumes belonging to a backup
            return instance, user_input, [system_volume_snapshot_id, data_volume_snapshot_id], None

        # if there were errors in input parameters
        errors = dict(serializer.errors)

        try:
            non_field_errors = errors.pop('non_field_errors')
            errors['detail'] = non_field_errors[0]
        except (KeyError, IndexError):
            pass

        return None, None, None, errors
