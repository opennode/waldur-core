from __future__ import unicode_literals

import re

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
import django_filters
from rest_framework import settings, filters
from rest_framework.serializers import ValidationError

from nodeconductor.core import serializers as core_serializers, filters as core_filters
from nodeconductor.core.filters import ExternalFilterBackend
from nodeconductor.logging import models, utils
from nodeconductor.logging.log import event_logger
from nodeconductor.logging.features import features_to_events, features_to_alerts, UPDATE_EVENTS


def _convert(name):
    """ Converts CamelCase to underscore """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class EventFilterBackend(filters.BaseFilterBackend):
    """ Sorting is supported in ascending and descending order by specifying a field to
        an **?o=** parameter. By default events are sorted by @timestamp in descending order.

        - ?o=\@timestamp

        Filtering of customer list is supported through HTTP query parameters, the following fields are supported:

        - ?event_type=<string> - type of filtered events. Can be list
        - ?search=<string> - text for FTS. FTS fields: 'message', 'customer_abbreviation', 'importance'
          'project_group_name', 'cloud_account_name', 'project_name'
        - ?scope=<URL> - url of object that is connected to event
        - ?scope_type=<string> - name of scope type of object that is connected to event (Ex.: project, customer...)
        - ?exclude_features=<feature> (can be list) - exclude event from output if
          it's type corresponds to one of listed features
    """

    def filter_queryset(self, request, queryset, view):
        search_text = request.query_params.get(settings.api_settings.SEARCH_PARAM, '')
        must_terms = {}
        must_not_terms = {}
        should_terms = {}
        if 'event_type' in request.query_params:
            must_terms['event_type'] = request.query_params.getlist('event_type')

        if 'exclude_features' in request.query_params:
            features = request.query_params.getlist('exclude_features')
            must_not_terms['event_type'] = features_to_events(features)

        if 'exclude_extra' in request.query_params:
            must_not_terms['event_type'] = must_not_terms.get('event_type', []) + UPDATE_EVENTS

        if 'scope' in request.query_params:
            field = core_serializers.GenericRelatedField(related_models=utils.get_loggable_models())
            field._context = {'request': request}
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

        queryset = queryset.filter(search_text=search_text,
                                   should_terms=should_terms,
                                   must_terms=must_terms,
                                   must_not_terms=must_not_terms)

        order_by = request.query_params.get('o', '-@timestamp')
        queryset = queryset.order_by(order_by)

        return queryset


class AlertFilter(django_filters.FilterSet):
    """ Basic filters for alerts """

    acknowledged = django_filters.BooleanFilter(name='acknowledged', distinct=True)
    closed_from = core_filters.TimestampFilter(name='closed', lookup_type='gte')
    closed_to = core_filters.TimestampFilter(name='closed', lookup_type='lt')
    created_from = core_filters.TimestampFilter(name='created', lookup_type='gte')
    created_to = core_filters.TimestampFilter(name='created', lookup_type='lt')
    content_type = core_filters.ContentTypeFilter()
    message = django_filters.CharFilter(lookup_type='icontains')

    class Meta:
        model = models.Alert
        fields = [
            'acknowledged',
            'closed_from',
            'closed_to',
            'created_from',
            'created_to',
            'content_type',
            'message'
        ]
        order_by = [
            'severity',
            '-severity',
            'created',
            '-created',
        ]


class AlertScopeFilterBackend(core_filters.GenericKeyFilterBackend):

    def get_related_models(self):
        return utils.get_loggable_models()

    def get_field_name(self):
        return 'scope'


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

        # XXX: this filter is wrong and deprecated, need to be removed after replacement in Portal
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

        if 'exclude_features' in request.query_params:
            features = request.query_params.getlist('exclude_features')
            queryset = queryset.exclude(alert_type__in=features_to_alerts(features))

        return queryset


class ExternalAlertFilterBackend(ExternalFilterBackend):
    pass
