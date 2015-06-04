import time

from rest_framework import serializers
from rest_framework.exceptions import ParseError

from nodeconductor.logging import models, utils
from nodeconductor.core.serializers import GenericRelatedField
from nodeconductor.core.fields import MappedChoiceField, JsonField
from nodeconductor.core.utils import timestamp_to_datetime
from nodeconductor.structure import models as structure_models
from nodeconductor.structure import filters as structure_filters
from nodeconductor.iaas.models import Instance

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
    def get_alerts(self, request):
        if 'aggregate' in request.query_params:
            alerts = self.filter_by_aggregate(request)
        else:
            alerts = models.Alert.objects.filtered_for_user(request.user)\
                                         .filter(closed__isnull=True)

        alerts = self.filter_by_time(request, alerts)
        return alerts

    def filter_by_time(self, request, alerts):
        day = 60 * 60 * 24
        start_timestamp = request.query_params.get('from', int(time.time() - day))
        start_datetime = self.parse_timestamp(start_timestamp)
        alerts = alerts.filter(created__gte=start_datetime)

        end_timestamp = request.query_params.get('to', int(time.time()))
        end_datetime = self.parse_timestamp(end_timestamp)
        alerts = alerts.filter(created__lte=end_datetime)

        return alerts

    def parse_timestamp(self, timestamp):
        try:
            return timestamp_to_datetime(timestamp)
        except ValueError:
            raise ParseError("Invalid timestamp value {}".format(timestamp))

    def filter_by_aggregate(self, request):
        def for_user(qs):
            return structure_filters.filter_queryset_for_user(qs, request.user)

        model_name = self.parse_model_name(request)
        uuid = request.query_params.get('uuid')

        aggregates = for_user(self.get_aggregates(model_name, uuid))
        instances = for_user(Instance.objects.for_aggregates(model_name, aggregates))
        alerts = for_user(models.Alert.objects.for_objects(instances))

        logger.debug(aggregates.query)
        logger.debug(instances.query)
        logger.debug(alerts.query)

        return alerts

    def parse_model_name(self, request):
        choices = ('customer', 'project', 'project_group')
        model_name = request.query_params.get('aggregate', 'customer')
        if model_name not in choices:
            raise ParseError("Invalid aggregate name. Available choices are {}".format(", ".join(choices)))
        return model_name

    def get_aggregates(self, model_name, uuid):
        MODEL_CLASSES = {
            'project': structure_models.Project,
            'customer': structure_models.Customer,
            'project_group': structure_models.ProjectGroup,
        }

        model = MODEL_CLASSES[model_name]
        queryset = model.objects.all()

        if uuid:
            queryset = queryset.filter(uuid=uuid)

        return queryset
