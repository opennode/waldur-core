from rest_framework import serializers

from nodeconductor.core.serializers import GenericRelatedField
from nodeconductor.core.fields import MappedChoiceField, JsonField
from nodeconductor.logging import models, utils, log


class AlertSerializer(serializers.HyperlinkedModelSerializer):
    scope = GenericRelatedField(related_models=utils.get_loggable_models())
    severity = MappedChoiceField(
        choices=[(v, k) for k, v in models.Alert.SeverityChoices.CHOICES],
        choice_mappings={v: k for k, v in models.Alert.SeverityChoices.CHOICES},
    )
    context = JsonField(read_only=True)

    class Meta(object):
        model = models.Alert
        fields = (
            'url', 'uuid', 'alert_type', 'message', 'severity', 'scope',
            'created', 'closed', 'context', 'acknowledged',
        )
        read_only_fields = ('uuid', 'created', 'closed')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def create(self, validated_data):
        alert, _ = log.AlertLogger().process(
            severity=validated_data['severity'],
            message_template=validated_data['message'],
            scope=validated_data['scope'],
            alert_type=validated_data['alert_type'],
        )
        return alert


class EventSerializer(serializers.Serializer):
    level = serializers.ChoiceField(choices=['debug', 'info', 'warning', 'error'])
    message = serializers.CharField()
    context = JsonField(required=False)


class BaseHookSerializer(serializers.HyperlinkedModelSerializer):
    event_types = serializers.MultipleChoiceField(choices=log.get_valid_events(), allow_blank=False)
    author_uuid = serializers.ReadOnlyField(source='user.uuid')
    hook_type = serializers.SerializerMethodField()

    class Meta(object):
        model = models.BaseHook

        fields = (
            'url', 'uuid', 'is_active', 'author_uuid', 'event_types', 'created', 'modified',
            'hook_type'
        )

        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super(BaseHookSerializer, self).create(validated_data)

    def validate(self, validated_data):
        validated_data['event_types'] = list(validated_data['event_types'])
        return validated_data

    def get_hook_type(self, hook):
        raise NotImplemented


class WebHookSerializer(BaseHookSerializer):
    content_type = MappedChoiceField(
        choices=[(v, v) for k, v in models.WebHook.ContentTypeChoices.CHOICES],
        choice_mappings={v: k for k, v in models.WebHook.ContentTypeChoices.CHOICES},
        required=False
    )

    class Meta(BaseHookSerializer.Meta):
        model = models.WebHook
        fields = BaseHookSerializer.Meta.fields + ('destination_url', 'content_type')

    def get_hook_type(self, hook):
        return 'webhook'


class EmailHookSerializer(BaseHookSerializer):

    class Meta(BaseHookSerializer.Meta):
        model = models.EmailHook
        fields = BaseHookSerializer.Meta.fields + ('email', )

    def get_hook_type(self, hook):
        return 'email'
