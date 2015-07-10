from __future__ import unicode_literals

import re

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db.models import Q
import django_filters
from rest_framework import generics, response, settings, viewsets, permissions, filters, status, decorators, mixins
from rest_framework.serializers import ValidationError

from nodeconductor.core import serializers as core_serializers, filters as core_filters
from nodeconductor.logging import elasticsearch_client, models, serializers, utils


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

        if 'scope_type' in request.query_params:
            def _convert(name):
                """ Converts CamelCase to underscore """
                s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
                return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

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
        return models.Alert.objects.filtered_for_user(self.request.user)

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


class HookViewSet(viewsets.ModelViewSet):
    queryset = models.Hook.objects.all()
    serializer_class = serializers.HookSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'uuid'

    def filter_queryset(self, queryset):
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(user=self.request.user)
