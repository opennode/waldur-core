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
        """
        To get a list of events - run **GET** against */api/events/* as authenticated user. Note that a user can
        only see events connected to objects she is allowed to see.

        Sorting is supported in ascending and descending order by specifying a field to an **?o=** parameter. By default
        events are sorted by @timestamp in descending order.

        Run POST against */api/events/* to create an event. Only users with staff privileges can create events.
        New event will be emitted with `custom_notification` event type.
        Request should contain following fields:

        - level: the level of current event. Following levels are supported: debug, info, warning, error
        - message: string representation of event message
        - scope: optional URL, which points to the loggable instance

        Request example:

        .. code-block:: javascript

            POST /api/events/
            Accept: application/json
            Content-Type: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "level": "info",
                "message": "message#1",
                "scope": "http://example.com/api/customers/9cd869201e1b4158a285427fcd790c1c/"
            }
        """
        self.queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(self.queryset)
        if page is not None:
            return self.get_paginated_response(page)
        return response.Response(self.queryset)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def perform_create(self, serializer):
        scope = serializer.validated_data.get('scope')
        context = {'scope': scope} if scope is not None else {}

        log.event_logger.custom.process(
            level=serializer.validated_data.get('level'),
            message_template=serializer.validated_data.get('message'),
            event_type='custom_notification',
            event_context=context,
            fail_silently=False
        )

    @decorators.list_route()
    def count(self, request, *args, **kwargs):
        """
        To get a count of events - run **GET** against */api/events/count/* as authenticated user.
        Endpoint support same filters as events list.

        Response example:

        .. code-block:: javascript

            {"count": 12321}
        """

        self.queryset = self.filter_queryset(self.get_queryset())
        return response.Response({'count': self.queryset.count()}, status=status.HTTP_200_OK)

    @decorators.list_route()
    def count_history(self, request, *args, **kwargs):
        """
        To get a historical data of events amount - run **GET** against */api/events/count/history/*.
        Endpoint support same filters as events list.
        More about historical data - read at section *Historical data*.

        Response example:

        .. code-block:: javascript

            [
                {
                    "point": 141111111111,
                    "object": {
                        "count": 558
                    }
                }
            ]
        """
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

    def list(self, request, *args, **kwargs):
        """
        To get a list of alerts, run **GET** against */api/alerts/* as authenticated user.

        Alert severity field can take one of this values: "Error", "Warning", "Info", "Debug".
        Field scope will contain link to object that cause alert.
        Context - dictionary that contains information about all related to alert objects.

        Run **POST** against */api/alerts/* to create or update alert. If alert with posted scope and
        alert_type already exists - it will be updated. Only users with staff privileges can create alerts.

        Request example:

        .. code-block:: javascript

            POST /api/alerts/
            Accept: application/json
            Content-Type: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "scope": "http://testserver/api/projects/b9e8a102b5ff4469b9ac03253fae4b95/",
                "message": "message#1",
                "alert_type": "first_alert",
                "severity": "Debug"
            }
        """
        return super(AlertViewSet, self).list(request, *args, **kwargs)

    @decorators.detail_route(methods=['post'])
    def close(self, request, *args, **kwargs):
        """
        To close alert - run **POST** against */api/alerts/<alert_uuid>/close/*. No data is required.
        Only users with staff privileges can close alerts.
        """
        if not request.user.is_staff:
            raise PermissionDenied()
        alert = self.get_object()
        alert.close()

        return response.Response(status=status.HTTP_204_NO_CONTENT)

    @decorators.detail_route(methods=['post'])
    def acknowledge(self, request, *args, **kwargs):
        """
        To acknowledge alert - run **POST** against */api/alerts/<alert_uuid>/acknowledge/*. No payload is required.
        All users that can see alerts can also acknowledge it. If alert is already acknowledged endpoint
        will return error with code 409(conflict).
        """
        alert = self.get_object()
        if not alert.acknowledged:
            alert.acknowledge()
            return response.Response(status=status.HTTP_200_OK)
        else:
            return response.Response({'detail': 'Alert is already acknowledged'}, status=status.HTTP_409_CONFLICT)

    @decorators.detail_route(methods=['post'])
    def cancel_acknowledgment(self, request, *args, **kwargs):
        """
        To cancel alert acknowledgment - run **POST** against */api/alerts/<alert_uuid>/cancel_acknowledgment/*.
        No payload is required. All users that can see alerts can also cancel it acknowledgment.
        If alert is not acknowledged endpoint will return error with code 409 (conflict).
        """
        alert = self.get_object()
        if alert.acknowledged:
            alert.cancel_acknowledgment()
            return response.Response(status=status.HTTP_200_OK)
        else:
            return response.Response({'detail': 'Alert is not acknowledged'}, status=status.HTTP_409_CONFLICT)

    @decorators.list_route()
    def stats(self, request, *args, **kwargs):
        """
        To get count of alerts per severities - run **GET** request against */api/alerts/stats/*.
        This endpoint supports all filters that are available for alerts list (*/api/alerts/*).

        Response example:

        .. code-block:: javascript

            {
                "debug": 2,
                "error": 1,
                "info": 1,
                "warning": 1
            }
        """
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

    def perform_create(self, serializer):
        if not self.request.user.is_staff:
            raise PermissionDenied('You do not have permission to perform this action.')

        super(AlertViewSet, self).perform_create(serializer)


class BaseHookViewSet(viewsets.ModelViewSet):
    """
    Hooks API allows user to receive event notifications via different channel, like email or webhook.
    To get a list of all your hooks, run **GET** against */api/hooks/* as an authenticated user.
    """
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (core_filters.StaffOrUserFilter,)
    lookup_field = 'uuid'


class WebHookViewSet(BaseHookViewSet):
    queryset = models.WebHook.objects.all()
    serializer_class = serializers.WebHookSerializer

    def list(self, request, *args, **kwargs):
        """
        To create new web hook issue **POST** against */api/hooks-web/* as an authenticated user.
        When hook is activated, **POST** request is issued against destination URL with the following data:

        .. code-block:: javascript

            {
                "timestamp": "2015-07-14T12:12:56.000000",
                "message": "Customer ABC LLC has been updated.",
                "type": "customer_update_succeeded",
                "context": {
                    "user_native_name": "Walter Lebrowski",
                    "customer_contact_details": "",
                    "user_username": "Walter",
                    "user_uuid": "1c3323fc4ae44120b57ec40dea1be6e6",
                    "customer_uuid": "4633bbbb0b3a4b91bffc0e18f853de85",
                    "ip_address": "8.8.8.8",
                    "user_full_name": "Walter Lebrowski",
                    "customer_abbreviation": "ABC LLC",
                    "customer_name": "ABC LLC"
                },
                "levelname": "INFO"
            }

        Note that context depends on event type.
        """
        return super(WebHookViewSet, self).list(request, *args, **kwargs)


class EmailHookViewSet(BaseHookViewSet):
    queryset = models.EmailHook.objects.all()
    serializer_class = serializers.EmailHookSerializer

    def list(self, request, *args, **kwargs):
        """
        To create new email hook issue **POST** against */api/hooks-email/* as an authenticated user.

        Example of a request:

        .. code-block:: javascript

            {
                "events": [
                    "iaas_instance_start_succeeded"
                ],
                "email": "test@example.com"
            }

        You may temporarily disable hook without deleting it by issuing following **PATCH** request against hook URL:

        .. code-block:: javascript

            {
                "is_active": "false"
            }
        """
        return super(EmailHookViewSet, self).list(request, *args, **kwargs)


class PushHookViewSet(BaseHookViewSet):
    queryset = models.PushHook.objects.all()
    serializer_class = serializers.PushHookSerializer

    def list(self, request, *args, **kwargs):
        """
        To create new push hook issue **POST** against */api/hooks-push/* as an authenticated user.

        Example of a request:

        .. code-block:: javascript

            {
                "events": [
                    "resource_start_succeeded"
                ],
                "type": "Android"
            }

        You may temporarily disable hook without deleting it by issuing following **PATCH** request against hook URL:

        .. code-block:: javascript

            {
                "is_active": "false"
            }
        """
        return super(PushHookViewSet, self).list(request, *args, **kwargs)


class HookSummary(BaseSummaryView):
    def get_urls(self, request):
        return ('webhook-list', 'emailhook-list', 'pushhook-list')
