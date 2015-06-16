from nodeconductor.logging.log import EventLogger, event_logger

class InstanceEventLogger(EventLogger):
    instance = 'iaas.Instance'
    volume_size = float
    flavor = 'iaas.Flavor'

    class Meta:
        nullable_fields = ('volume_size', 'flavor')

        event_types = (
            'iaas_instance_start_scheduled',
            'iaas_instance_start_succeeded',
            'iaas_instance_start_failed',

            'iaas_instance_stop_scheduled',
            'iaas_instance_stop_failed',
            'iaas_instance_stop_succeeded',

            'iaas_instance_restart_scheduled',
            'iaas_instance_restart_succeeded',
            'iaas_instance_restart_failed',

            'iaas_instance_creation_scheduled',
            'iaas_instance_creation_succeeded',
            'iaas_instance_creation_failed',
            'iaas_instance_update_succeeded',

            'iaas_instance_deletion_scheduled',
            'iaas_instance_deletion_succeeded',
            'iaas_instance_deletion_failed',

            'iaas_instance_volume_extension_scheduled',
            'iaas_instance_volume_extension_succeeded',
            'iaas_instance_volume_extension_failed',

            'iaas_instance_flavor_change_scheduled',
            'iaas_instance_flavor_change_succeeded',
            'iaas_instance_flavor_change_failed',
        )


class InstanceImportEventLogger(EventLogger):
    instance_id = basestring

    class Meta:
        event_types = (
            'iaas_instance_import_scheduled',
            'iaas_instance_import_succeeded',
            'iaas_instance_import_failed',
        )


class MembershipEventLogger(EventLogger):
    cloud = 'iaas.Cloud'
    project = 'structure.Project'
    ssh_key = 'core.SshPublicKey'

    class Meta:
        nullable_fields = ['ssh_key']

        event_types = (
            'iaas_sync_membership_ssh_key_failed',
            'iaas_sync_membership_security_group_failed',
        )


class QuotaEventLogger(EventLogger):
    quota = 'quotas.Quota'
    cloud = 'iaas.Cloud'
    project = 'structure.Project'
    project_group = 'structure.ProjectGroup'
    threshold = float
    usage = float

    class Meta:
        event_types = (
            'quota_threshold_reached',
        )


event_logger.register('instance', InstanceEventLogger)
event_logger.register('instance_import', InstanceImportEventLogger)
event_logger.register('membership', MembershipEventLogger)
event_logger.register('quota', QuotaEventLogger)
