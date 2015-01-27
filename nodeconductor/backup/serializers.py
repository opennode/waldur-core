from rest_framework import serializers

from nodeconductor.backup import models, utils
from nodeconductor.core.serializers import GenericRelatedField
from nodeconductor.structure.serializers import fix_non_nullable_attrs


class BackupScheduleSerializer(serializers.HyperlinkedModelSerializer):
    backup_source = GenericRelatedField(related_models=utils.get_backupable_models())

    class Meta(object):
        model = models.BackupSchedule
        fields = ('url', 'description', 'backups', 'retention_time', 'backup_source',
                  'maximal_number_of_backups', 'schedule', 'is_active')
        read_only_fields = ('is_active', 'backups')
        lookup_field = 'uuid'

    # TODO: cleanup after migration to drf 3
    def validate(self, attrs):
        return fix_non_nullable_attrs(attrs)


class BackupSerializer(serializers.HyperlinkedModelSerializer):
    backup_source = GenericRelatedField(related_models=utils.get_backupable_models())
    state = serializers.ChoiceField(choices=models.Backup.STATE_CHOICES, source='get_state_display', read_only=True)

    class Meta(object):
        model = models.Backup
        fields = ('url', 'description', 'created_at', 'kept_until', 'backup_source', 'state', 'backup_schedule')
        read_only_fields = ('created_at', 'kept_until', 'backup_schedule')
        lookup_field = 'uuid'

    # TODO: cleanup after migration to drf 3
    def validate(self, attrs):
        return fix_non_nullable_attrs(attrs)
