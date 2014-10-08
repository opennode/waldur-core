from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse, resolve, Resolver404

from rest_framework import serializers
from rest_framework.relations import RelatedField

from nodeconductor.backup import models


class RelatedBackupField(RelatedField):
    """
    A custom field to use for the `tagged_object` generic relationship.
    """
    read_only = False
    _default_view_name = '%(model_name)s-detail'
    lookup_field = 'uuid'

    def _get_url(self, obj):
        """
        Gets object url
        """
        format_kwargs = {
            'app_label': obj._meta.app_label,
            'model_name': obj._meta.object_name.lower()
        }
        return self._default_view_name % format_kwargs

    def to_native(self, obj):
        """
        Serialize any object to his url representation
        """
        kwargs = {self.lookup_field: getattr(obj, self.lookup_field)}
        return reverse(self._get_url(obj), kwargs=kwargs)

    def _format_url(self, url):
        """
        Removes domain and protocol from url
        """
        if url.startswith('http'):
            return '/' + url.split('/', 3)[-1]
        return url

    def _get_model_from_resolve_match(self, match):
        queryset = match.func.cls.queryset
        if queryset is not None:
            return queryset.model
        else:
            return match.func.cls.model

    def from_native(self, data):
        """
        Restores model instance from its url
        """
        try:
            url = self._format_url(data)
            match = resolve(url)
            model = self._get_model_from_resolve_match(match)
            obj = model.objects.get(**match.kwargs)
        except Resolver404:
            raise ObjectDoesNotExist("Can`t restore object from url: {}".format(data))
        return obj


class BackupScheduleSerializer(serializers.HyperlinkedModelSerializer):
    backup_source = RelatedBackupField()

    class Meta(object):
        model = models.BackupSchedule
        fields = ('url', 'description', 'backups', 'retention_time', 'backup_source')
        lookup_field = 'uuid'


class BackupSerializer(serializers.HyperlinkedModelSerializer):
    backup_source = RelatedBackupField()

    class Meta(object):
        model = models.Backup
        fields = ('url', 'description', 'created_at', 'kept_until', 'backup_source')
        lookup_field = 'uuid'
