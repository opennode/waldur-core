from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse, resolve, Resolver404
from django.db.models.query import EmptyQuerySet
from nodeconductor.structure.serializers import fix_non_nullable_attrs

from rest_framework import serializers
from rest_framework.relations import RelatedField

from nodeconductor.backup import models, utils


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
        Serializes any object to his url representation
        """
        kwargs = {self.lookup_field: getattr(obj, self.lookup_field)}
        try:
            request = self.context['request']
        except AttributeError:
            raise AttributeError('RelatedBackupField have to be initialized with `request` in context')
        return request.build_absolute_uri(reverse(self._get_url(obj), kwargs=kwargs))

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
            raise ValidationError("Can`t restore object from url: %s" % data)
        if not utils.has_object_backup_strategy(obj):
            raise ValidationError('%s object is unbackupable' % str(obj))
        return obj

    # this method tries to initialize queryset based on field.rel.to._default_manager
    # but generic field does not have default manager
    def initialize(self, parent, field_name):
        super(RelatedField, self).initialize(parent, field_name)

        supported_models = utils.get_backup_strategies().values()
        if len(supported_models) < 1:
            # XXX: setting queryset to None is not the best idea. Better empty set models are welcome
            self.queryset = None
            return

        # XXX ideally this queryset has to return all available for generic key instances
        # Now we just take first backupable model and return all its instances
        model = supported_models[0].get_model()
        self.queryset = model.objects.all()


class BackupScheduleSerializer(serializers.HyperlinkedModelSerializer):
    backup_source = RelatedBackupField()

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
    backup_source = RelatedBackupField()
    state = serializers.ChoiceField(choices=models.Backup.STATE_CHOICES, source='get_state_display', read_only=True)

    class Meta(object):
        model = models.Backup
        fields = ('url', 'description', 'created_at', 'kept_until', 'backup_source', 'state', 'backup_schedule')
        read_only_fields = ('created_at', 'kept_until', 'backup_schedule')
        lookup_field = 'uuid'

    # TODO: cleanup after migration to drf 3
    def validate(self, attrs):
        return fix_non_nullable_attrs(attrs)
