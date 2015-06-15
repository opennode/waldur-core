import re

from rest_framework import serializers

from nodeconductor.core.serializers import GenericRelatedField
from nodeconductor.core.fields import MappedChoiceField, JsonField
from nodeconductor.logging import models, utils


class AlertSerializer(serializers.HyperlinkedModelSerializer):
    scope = GenericRelatedField(related_models=utils.get_loggable_models(), read_only=True)
    severity = MappedChoiceField(
        choices=[(v, k) for k, v in models.Alert.SeverityChoices.CHOICES],
        choice_mappings={v: k for k, v in models.Alert.SeverityChoices.CHOICES},
        read_only=True,
    )
    context = JsonField()

    class Meta(object):
        model = models.Alert
        fields = ('url', 'uuid', 'alert_type', 'message', 'severity', 'scope', 'created', 'closed', 'context')
        read_only_fields = ('uuid', 'created', 'closed')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


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
