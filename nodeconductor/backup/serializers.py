from rest_framework import serializers
from rest_framework.relations import RelatedField

from nodeconductor.backup import models
from nodeconductor.core.fields import HyperlinkedGenericRelatedField


class RelatedBackupField(RelatedField):
    def __init__(self, *args, **kwargs):
        super(RelatedBackupField, self).__init__(*args, **kwargs)

    def get_related_object_url(self, obj):
        obj = obj
        default_view_name = '%(model_name)s-detail'
        format_kwargs = {
            'app_label': obj._meta.app_label,
            'model_name': obj._meta.object_name.lower()
        }
        view_name = default_view_name % format_kwargs
        s = serializers.HyperlinkedIdentityField(source=obj, view_name=view_name, lookup_field='uuid')
        s.initialize(self, None)
        return s.field_to_native(obj, None)

    def to_native(self, value):
        url = self.get_related_object_url(value)
        return url


class BackupScheduleSerializer(serializers.HyperlinkedModelSerializer):
    backup_source = RelatedBackupField()
    #backup_target =

    class Meta(object):
        model = models.BackupSchedule
        fields = ('url', 'description', 'backups', 'backup_source', 'retention_time')
        lookup_field = 'uuid'


class BackupSerializer(serializers.HyperlinkedModelSerializer):
    backup_source = RelatedBackupField()

    #backup_target = HyperlinkedGenericRelatedField()

    class Meta(object):
        model = models.Backup
        fields = ('url', 'description', 'created_at', 'backup_source', 'kept_until')
        lookup_field = 'uuid'
