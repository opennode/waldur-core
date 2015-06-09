import arrow

from nodeconductor.core.fields import TimestampField
from nodeconductor.core.utils import timeshift
from nodeconductor.quotas.models import QuotaLog
from nodeconductor.structure.filters import filter_queryset_for_user
from nodeconductor.structure.models import Project
from rest_framework import serializers

from nodeconductor.quotas import models, utils
from nodeconductor.core.serializers import GenericRelatedField

import logging
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)

class QuotaSerializer(serializers.HyperlinkedModelSerializer):
    scope = GenericRelatedField(related_models=utils.get_models_with_quotas(), read_only=True)

    class Meta(object):
        model = models.Quota
        fields = ('url', 'uuid', 'name', 'limit', 'usage', 'scope')
        read_only_fields = ('uuid', 'name', 'usage')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

class QuotaTimelineStatsSerializer(serializers.Serializer):

    INTERVAL_CHOICES = ('day', 'week', 'month')

    start_time = TimestampField(default=lambda: timeshift(days=-1))
    end_time = TimestampField(default=lambda: timeshift())
    interval = serializers.ChoiceField(choices=INTERVAL_CHOICES, default='day')
    scope = serializers.CharField()
    item = serializers.CharField(required=False)

    def get_stats(self, user):
        logger.debug("Query quota timeline statistics for %s", self.data)

        qs = QuotaLog.objects.for_object(self.get_scope(user))
        spans = self.get_spans()
        items = self.get_items()

        return [self.make_row(span, items, qs) for span in spans]

    def get_scope(self, user):
        uuid = self.data['scope']
        try:
            return filter_queryset_for_user(Project.objects, user).get(uuid=uuid)
        except Project.DoesNotExist:
            raise ValidationError({"scope": "Scope with such UUID is not found."})

    def make_row(self, span, items, qs):
        start_time, end_time = span
        row = {
            'from': start_time.timestamp,
            'to': end_time.timestamp,
        }
        for item in items:
            qs1 = qs.filter(created__gte=start_time.datetime,
                            created__lte=end_time.datetime,
                            quota__name=item)\
                    .order_by('-created').values('limit', 'usage')
            logger.debug("Query quota stats for interval and item %s", qs1.query)
            value = qs1.first()
            if value:
                row[item] = value['limit']
                row[item + '_usage'] = value['usage']
        return row

    def get_items(self):
        item = self.validated_data.get('item')
        if item is None:
            items = Project.QUOTAS_NAMES
        else:
            items = [item]
        return items

    def get_spans(self):
        start_time = self.validated_data['start_time']
        end_time = self.validated_data['end_time']
        if end_time < start_time:
            raise ValidationError({"to": "Invalid time frame."})
        interval = self.data['interval']
        return arrow.Arrow.span_range(interval, start_time, end_time)
