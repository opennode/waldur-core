import re

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


class ScopeSerializer(serializers.Serializer):
    scope = GenericRelatedField(related_models=utils.get_loggable_models())


def _convert(name):
    """ Converts CamelCase to underscore """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class ScopeTypeSerializer(serializers.Serializer):
    scope_type = MappedChoiceField(
        choices=[(_convert(m.__name__), m.__name__) for m in utils.get_loggable_models()],
        choice_mappings={_convert(m.__name__): m for m in utils.get_loggable_models()},
    )
