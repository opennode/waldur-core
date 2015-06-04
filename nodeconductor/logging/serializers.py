from rest_framework import serializers

from nodeconductor.logging import models, utils
from nodeconductor.core.serializers import GenericRelatedField
from nodeconductor.core.fields import MappedChoiceField, JsonField
from nodeconductor.core.utils import timestamp_to_datetime
from rest_framework.exceptions import ParseError


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


class StatsQuerySerializer(serializers.Serializer):
    start_timestamp = serializers.IntegerField(min_value=0, required=False)
    end_timestamp = serializers.IntegerField(min_value=0, required=False)

    def get_alerts(self, user):
        # instances = filter_queryset_for_user(Instance.objects.all(), request.user)
        # alerts = models.Alert.objects.for_objects(instances)
        alerts = models.Alert.objects.filtered_for_user(user)\
                                     .filter(closed__isnull=True)

        if self.data.get('start_timestamp', 0):
            start_datetime = self.parse_timestamp(self.data['start_timestamp'])
            alerts = alerts.filter(created__gte=start_datetime)

        if self.data.get('end_timestamp', 0):
            end_datetime = self.parse_timestamp(self.data['end_timestamp'])
            alerts = alerts.filter(created__lte=end_datetime)

        return alerts

    def parse_timestamp(self, timestamp):
        try:
            return timestamp_to_datetime(timestamp)
        except ValueError:
            raise ParseError("Invalid start_timestamp")
