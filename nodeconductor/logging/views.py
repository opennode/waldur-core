from __future__ import unicode_literals

from django.db.models import Count
from rest_framework import generics, response, settings, views, viewsets, permissions, status

from nodeconductor.logging import elasticsearch_client, models, serializers
from nodeconductor.core.utils import sort_dict
from nodeconductor.iaas.models import Instance
from nodeconductor.structure.filters import filter_queryset_for_user

class EventListView(generics.GenericAPIView):

    ADDITIONAL_SEARCH_FIELDS = ['user_uuid', 'customer_uuid', 'project_uuid', 'project_group_uuid']

    def get_queryset(self, request):
        return elasticsearch_client.ElasticsearchResultList(request.user)

    def filter(self, request):
        search_text = request.query_params.get(settings.api_settings.SEARCH_PARAM)
        event_types = request.query_params.getlist('event_type')
        search_kwargs = {field: request.query_params.get(field)
                         for field in self.ADDITIONAL_SEARCH_FIELDS if field in request.query_params}
        self.queryset = self.queryset.filter(
            event_types=event_types,
            search_text=search_text,
            **search_kwargs)

    def order(self, request):
        order_by = request.query_params.get('o', '-@timestamp')
        self.queryset = self.queryset.order_by(order_by)

    def list(self, request, *args, **kwargs):
        self.queryset = self.get_queryset(request)
        self.filter(request)
        self.order(request)

        page = self.paginate_queryset(self.queryset)
        if page is not None:
            return self.get_paginated_response(page)
        return response.Response(self.queryset)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class AlertViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = models.Alert.objects.all()
    serializer_class = serializers.AlertSerializer
    lookup_field = 'uuid'
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return models.Alert.objects.filtered_for_user(self.request.user)


class AlertStatsView(views.APIView):
    def get(self, request):
        """
        Counts health statistics based on the alert number and severity
        Example response:
        {
            "Debug": 2,
            "Error": 1,
            "Info": 1,
            "Warning": 1
        }
        """
        serializer = serializers.StatsQuerySerializer()
        alerts = serializer.get_alerts(request)

        items = alerts.values('severity').annotate(count=Count('severity'))
        stats = self.format_result(items)

        return response.Response(stats, status=status.HTTP_200_OK)

    def format_result(self, items):
        choices = dict(models.Alert.SeverityChoices.CHOICES)
        stat = {}
        for item in items:
            key = item['severity']
            label = choices[key]
            stat[label] = item['count']
        return sort_dict(stat)
