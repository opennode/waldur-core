from rest_framework import serializers

from nodeconductor.monitoring.models import MonitoringItem


class MonitoringItemSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = MonitoringItem
        fields = ('name', 'value')
        read_only_fields = ('name', 'value')
