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
    status = serializers.ChoiceField(
        choices=(('PROBLEM', 'Problem'), ('OK', 'OK')), default='PROBLEM', write_only=True)

    class Meta(object):
        model = models.Alert
        fields = (
            'url', 'uuid', 'alert_type', 'message', 'severity', 'scope', 'created', 'closed', 'context', 'status')
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
