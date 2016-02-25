from __future__ import unicode_literals

from django.core.exceptions import PermissionDenied
from django.db.models import Count
from rest_framework import response, viewsets, permissions, status, decorators, mixins

from nodeconductor.core import serializers as core_serializers, filters as core_filters, permissions as core_permissions
from nodeconductor.core.views import BaseSummaryView
from nodeconductor.logging import elasticsearch_client, models, serializers, filters, log


class EventViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):

    permission_classes = (permissions.IsAuthenticated, core_permissions.IsAdminOrReadOnly)
    filter_backends = (filters.EventFilterBackend,)
    serializer_class = serializers.EventSerializer

    def get_queryset(self):
        return elasticsearch_client.ElasticsearchResultList()

    def list(self, request, *args, **kwargs):
        self.queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(self.queryset)
        if page is not None:
            return self.get_paginated_response(page)
        return response.Response(self.queryset)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def perform_create(self, serializer):
        log.EventLogger().process(
            level=serializer.validated_data.get('level'),
            message_template=serializer.validated_data.get('message'),
            event_type='custom_notification',
            event_context=serializer.validated_data.get('context')
        )

    @decorators.list_route()
    def count(self, request, *args, **kwargs):
        self.queryset = self.filter_queryset(self.get_queryset())
        return response.Response({'count': self.queryset.count()}, status=status.HTTP_200_OK)

    @decorators.list_route()
    def count_history(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        mapped = {
            'start': request.query_params.get('start'),
            'end': request.query_params.get('end'),
            'points_count': request.query_params.get('points_count'),
            'point_list': request.query_params.getlist('point'),
        }
        serializer = core_serializers.HistorySerializer(data={k: v for k, v in mapped.items() if v})
        serializer.is_valid(raise_exception=True)

        timestamp_ranges = [{'end': point_date} for point_date in serializer.get_filter_data()]
        aggregated_count = queryset.aggregated_count(timestamp_ranges)

        return response.Response(
            [{'point': int(ac['end']), 'object': {'count': ac['count']}} for ac in aggregated_count],
            status=status.HTTP_200_OK)


class AlertViewSet(mixins.CreateModelMixin,
                   viewsets.ReadOnlyModelViewSet):

    queryset = models.Alert.objects.all()
    serializer_class = serializers.AlertSerializer
    lookup_field = 'uuid'
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (
        core_filters.DjangoMappingFilterBackend,
        filters.AdditionalAlertFilterBackend,
        filters.ExternalAlertFilterBackend,
        filters.AlertScopeFilterBackend,
    )
    filter_class = filters.AlertFilter

    def get_queryset(self):
        return models.Alert.objects.filtered_for_user(self.request.user).order_by('-created')

    @decorators.detail_route(methods=['post'])
    def close(self, request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied()
        alert = self.get_object()
        alert.close()

        return response.Response(status=status.HTTP_204_NO_CONTENT)

    @decorators.detail_route(methods=['post'])
    def acknowledge(self, request, *args, **kwargs):
        alert = self.get_object()
        if not alert.acknowledged:
            alert.acknowledge()
            return response.Response(status=status.HTTP_200_OK)
        else:
            return response.Response({'detail': 'Alert is already acknowledged'}, status=status.HTTP_409_CONFLICT)

        return response.Response(status=status.HTTP_200_OK)

    @decorators.detail_route(methods=['post'])
    def cancel_acknowledgment(self, request, *args, **kwargs):
        alert = self.get_object()
        if alert.acknowledged:
            alert.cancel_acknowledgment()
            return response.Response(status=status.HTTP_200_OK)
        else:
            return response.Response({'detail': 'Alert is not acknowledged'}, status=status.HTTP_409_CONFLICT)

    @decorators.list_route()
    def stats(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        alerts_severities_count = queryset.values('severity').annotate(count=Count('severity'))

        severity_names = dict(models.Alert.SeverityChoices.CHOICES)
        # For consistency with all other endpoint we need to return severity names in lower case.
        alerts_severities_count = {
            severity_names[asc['severity']].lower(): asc['count'] for asc in alerts_severities_count}
        for severity_name in severity_names.values():
            if severity_name.lower() not in alerts_severities_count:
                alerts_severities_count[severity_name.lower()] = 0

        return response.Response(alerts_severities_count, status=status.HTTP_200_OK)


class BaseHookViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (core_filters.StaffOrUserFilter,)
    lookup_field = 'uuid'


class WebHookViewSet(BaseHookViewSet):
    queryset = models.WebHook.objects.all()
    serializer_class = serializers.WebHookSerializer


class EmailHookViewSet(BaseHookViewSet):
    queryset = models.EmailHook.objects.all()
    serializer_class = serializers.EmailHookSerializer


class HookSummary(BaseSummaryView):
    def get_urls(self, request):
        return ('webhook-list', 'emailhook-list')
