from collections import defaultdict
from rest_framework import serializers

from .models import ResourceItem, ResourceSla
from .utils import get_period, to_list


class ResourceSlaStateTransitionSerializer(serializers.Serializer):
    timestamp = serializers.IntegerField()
    state = serializers.SerializerMethodField()

    def get_state(self, obj):
        return obj.state and 'U' or 'D'


class MonitoringSerializerMixin(serializers.Serializer):
    sla = serializers.SerializerMethodField()
    monitoring_items = serializers.SerializerMethodField()

    class Meta:
        fields = ('sla', 'monitoring_items')

    def get_sla(self, resource):
        if not hasattr(self, 'sla_map_cache'):
            self.sla_map_cache = {}
            request = self.context['request']

            items = ResourceSla.objects.filter(scope__in=to_list(self.instance))
            items = items.filter(period=get_period(request))
            for item in items:
                self.sla_map_cache[item.object_id] = dict(
                    value=item.value,
                    agreed_value=item.agreed_value,
                    period=item.period
                )

        return self.sla_map_cache.get(resource.id)

    def get_monitoring_items(self, resource):
        if 'monitoring_items' not in self.context:
            items = ResourceItem.objects.filter(scope__in=to_list(self.instance))

            monitoring_items = defaultdict(dict)
            for item in items:
                monitoring_items[item.object_id][item.name] = item.value

            self.context['monitoring_items'] = monitoring_items
        return self.context['monitoring_items'].get(resource.id)
