import time

from django.db.models import Count
from rest_framework import serializers
from rest_framework.exceptions import ParseError

from nodeconductor.logging import models, utils
from nodeconductor.core.serializers import GenericRelatedField
from nodeconductor.core.fields import MappedChoiceField, JsonField, TimestampField
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.filters import filter_queryset_for_user
from nodeconductor.iaas.models import Instance
from nodeconductor.core.utils import sort_dict, timeshift

import logging
logger = logging.getLogger(__name__)

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
    start_time = TimestampField(default=lambda: timeshift(days=-1))
    end_time = TimestampField(default=lambda: timeshift())

    model = MappedChoiceField(
        choices=(
            ('project', 'project'),
            ('customer', 'customer'),
            ('project_group', 'project_group')
        ),
        choice_mappings={
            'project': structure_models.Project,
            'customer': structure_models.Customer,
            'project_group': structure_models.ProjectGroup,
        },
        required=False
    )
    uuid = serializers.CharField(required=False)

    def get_stats(self, user):
        """
        Count alerts by severity
        """
        logger.debug("Query alerts statistics %s", self.data)
        alerts = self.get_alerts(user)
        items = alerts.values('severity').annotate(count=Count('severity'))
        return self.format_result(items)

    def format_result(self, items):
        choices = dict(models.Alert.SeverityChoices.CHOICES)
        stat = {val: 0 for key, val in choices.items()}
        for item in items:
            key = item['severity']
            label = choices[key]
            stat[label] = item['count']
        return sort_dict(stat)

    def get_alerts(self, user):
        if 'model' in self.data and 'uuid' in self.data:
            alerts = self.get_alerts_for_aggregate(user)
        else:
            alerts = models.Alert.objects.filtered_for_user(user)\
                                         .filter(closed__isnull=True)

        return alerts.filter(created__gte=self.validated_data['start_time'])\
                     .filter(created__lte=self.validated_data['end_time'])

    def get_alerts_for_aggregate(self, user):
        uuid = self.data['uuid']
        model = self.validated_data['model']
        aggregates = filter_queryset_for_user(
            model.objects.filter(uuid=uuid), user)

        model_name = self.data['model']
        instances = filter_queryset_for_user(
            Instance.objects.for_aggregates(model_name, aggregates), user)

        alerts = filter_queryset_for_user(
            models.Alert.objects.for_objects(instances), user)
        logger.debug("Query alerts for instances %s", alerts.query)
        return alerts
