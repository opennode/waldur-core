from __future__ import unicode_literals

import re

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Count
import django_filters
from rest_framework import response, settings, viewsets, permissions, filters, status, decorators, mixins
from rest_framework.serializers import ValidationError

from nodeconductor.core import serializers as core_serializers, filters as core_filters
from nodeconductor.logging import elasticsearch_client, models, serializers, utils
from nodeconductor.logging.log import event_logger


def _convert(name):
    """ Converts CamelCase to underscore """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class EventFilterBackend(filters.BaseFilterBackend):

    def filter_queryset(self, request, queryset, view):
        search_text = request.query_params.get(settings.api_settings.SEARCH_PARAM, '')
        must_terms = {}
        should_terms = {}
        if 'event_type' in request.query_params:
            must_terms['event_type'] = request.query_params.getlist('event_type')

        if 'scope' in request.query_params:
            field = core_serializers.GenericRelatedField(related_models=utils.get_loggable_models())
            obj = field.to_internal_value(request.query_params['scope'])
            must_terms[_convert(obj.__class__.__name__ + '_uuid')] = [obj.uuid.hex]
        elif 'scope_type' in request.query_params:
            choices = {_convert(m.__name__): m for m in utils.get_loggable_models()}
            try:
                scope_type = choices[request.query_params['scope_type']]
            except KeyError:
                raise ValidationError(
                    'Scope type "{}" is not valid. Has to be one from list: {}'.format(
                        request.query_params['scope_type'], ', '.join(choices.keys()))
                )
            else:
                must_terms.update(scope_type.get_permitted_objects_uuids(request.user))
        else:
            should_terms.update(event_logger.get_permitted_objects_uuids(request.user))

        queryset = queryset.filter(search_text=search_text, should_terms=should_terms, must_terms=must_terms)

        order_by = request.query_params.get('o', '-@timestamp')
        queryset = queryset.order_by(order_by)

        return queryset


class EventViewSet(viewsets.GenericViewSet):

    filter_backends = (EventFilterBackend,)

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


class AlertFilter(django_filters.FilterSet):
    """ Basic filters for alerts """

    acknowledged = django_filters.BooleanFilter(name='acknowledged', distinct=True)
    scope = core_filters.GenericKeyFilter(related_models=utils.get_loggable_models())
    closed_from = core_filters.TimestampFilter(name='closed', lookup_type='gte')
    closed_to = core_filters.TimestampFilter(name='closed', lookup_type='lt')
    created_from = core_filters.TimestampFilter(name='created', lookup_type='gte')
    created_to = core_filters.TimestampFilter(name='created', lookup_type='lt')

    class Meta:
        model = models.Alert
        fields = [
            'acknowledged',
            'scope',
            'closed_from',
            'closed_to',
            'created_from',
            'created_to',
        ]
        order_by = [
            'severity',
            '-severity',
            'created',
            '-created',
        ]


class AdditionalAlertFilterBackend(filters.BaseFilterBackend):
    """
    Additional filters for alerts.

    Support for filters that are related to more than one field or provides unusual query.
    """

    def filter_queryset(self, request, queryset, view):
        mapped = {
            'start': request.query_params.get('from'),
            'end': request.query_params.get('to'),
        }
        timestamp_interval_serializer = core_serializers.TimestampIntervalSerializer(
            data={k: v for k, v in mapped.items() if v})
        timestamp_interval_serializer.is_valid(raise_exception=True)
        filter_data = timestamp_interval_serializer.get_filter_data()
        if 'start' in filter_data:
            queryset = queryset.filter(
                Q(closed__gte=filter_data['start']) | Q(closed__isnull=True))
        if 'end' in filter_data:
            queryset = queryset.filter(created__lte=filter_data['end'])

        if 'opened' in request.query_params:
            queryset = queryset.filter(closed__isnull=True)

        if 'severity' in request.query_params:
            severity_codes = {v: k for k, v in models.Alert.SeverityChoices.CHOICES}
            severities = [
                severity_codes.get(severity_name) for severity_name in request.query_params.getlist('severity')]
            queryset = queryset.filter(severity__in=severities)

        # XXX: this filtering is fragile, need to be fixed in NC-774
        if 'scope_type' in request.query_params:
            choices = {_convert(m.__name__): m for m in utils.get_loggable_models()}
            try:
                scope_type = choices[request.query_params['scope_type']]
            except KeyError:
                raise ValidationError(
                    'Scope type "{}" is not valid. Has to be one from list: {}'.format(
                        request.query_params['scope_type'], ', '.join(choices.keys()))
                )
            else:
                ct = ContentType.objects.get_for_model(scope_type)
                queryset = queryset.filter(content_type=ct)

        if 'alert_type' in request.query_params:
            queryset = queryset.filter(alert_type__in=request.query_params.getlist('alert_type'))

        return queryset


class BaseExternalFilter(object):
    """ Interface for external alert filter """
    def filter(self, request, queryset, view):
        raise NotImplementedError


class ExternalAlertFilterBackend(filters.BaseFilterBackend):
    """
    Support external filters registered in other apps
    """

    @classmethod
    def get_registered_filters(cls):
        return getattr(cls, '_filters', [])

    @classmethod
    def register(cls, external_filter):
        assert isinstance(external_filter, BaseExternalFilter), 'Registered filter has to inherit BaseExternalFilter'
        if hasattr(cls, '_filters'):
            cls._filters.append(external_filter)
        else:
            cls._filters = [external_filter]

    def filter_queryset(self, request, queryset, view):
        for filt in self.__class__.get_registered_filters():
            queryset = filt.filter(request, queryset, view)
        return queryset


class AlertViewSet(mixins.CreateModelMixin,
                   viewsets.ReadOnlyModelViewSet):

    queryset = models.Alert.objects.all()
    serializer_class = serializers.AlertSerializer
    lookup_field = 'uuid'
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (filters.DjangoFilterBackend, AdditionalAlertFilterBackend, ExternalAlertFilterBackend)
    filter_class = AlertFilter

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
