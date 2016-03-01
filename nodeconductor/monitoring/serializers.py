from collections import defaultdict
from rest_framework import serializers

from .models import ResourceItem, ResourceSla
from .utils import get_period, filter_for_qs


class ResourceStateSerializer(serializers.Serializer):
    timestamp = serializers.IntegerField()
    state = serializers.SerializerMethodField()

    def get_state(self, obj):
        return obj.state and 'U' or 'D'


class MonitoringSerializerMixin(serializers.Serializer):
    actual_sla = serializers.SerializerMethodField()
    monitoring_items = serializers.SerializerMethodField()

    class Meta:
        fields = ('actual_sla', 'monitoring_items')

    def get_actual_sla(self, resource):
        if 'sla_map' not in self.context:
            request = self.context['request']
            items = filter_for_qs(ResourceSla, self.instance)
            items = items.filter(period=get_period(request))
            sla_map = {item.object_id: item.value for item in items}

            self.context['sla_map'] = sla_map
        return self.context['sla_map'].get(resource.id)

    def get_monitoring_items(self, resource):
        if 'monitoring_items' not in self.context:
            items = filter_for_qs(ResourceItem, self.instance)

            monitoring_items = defaultdict(dict)
            for item in items:
                monitoring_items[item.object_id][item.name] = item.value

            self.context['monitoring_items'] = monitoring_items
        return self.context['monitoring_items'].get(resource.id)
