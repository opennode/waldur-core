from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from rest_framework import generics, response, settings, viewsets, permissions, filters, status, decorators, mixins
from rest_framework.serializers import ValidationError

from nodeconductor.core import utils as core_utils
from nodeconductor.logging import elasticsearch_client, models, serializers


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


class AlertFilter(filters.BaseFilterBackend):
    """  """

    def filter_queryset(self, request, queryset, view):
        # TODO: get rid of circular dependency between iaas, structure and logging.
        from nodeconductor.iaas import serializers as iaas_serializers, models as iaas_models
        from nodeconductor.structure import models as structure_models

        aggregate_serializer = iaas_serializers.StatsAggregateSerializer(data=request.query_params)
        aggregate_serializer.is_valid(raise_exception=True)

        projects_ids = aggregate_serializer.get_projects(request.user).values_list('id', flat=True)
        instances_ids = aggregate_serializer.get_instances(request.user).values_list('id', flat=True)
        memebersips_ids = aggregate_serializer.get_memberships(request.user).values_list('id', flat=True)

        aggregate_query = Q(
            content_type=ContentType.objects.get_for_model(structure_models.Project),
            object_id__in=projects_ids
        )
        aggregate_query |= Q(
            content_type=ContentType.objects.get_for_model(iaas_models.Instance),
            object_id__in=instances_ids
        )
        aggregate_query |= Q(
            content_type=ContentType.objects.get_for_model(iaas_models.CloudProjectMembership),
            object_id__in=memebersips_ids
        )
        queryset = queryset.filter(aggregate_query)

        if 'scope' in request.query_params:
            scope_serializer = serializers.ScopeSerializer(data=request.query_params)
            scope_serializer.is_valid(raise_exception=True)
            scope = scope_serializer.validated_data['scope']
            ct = ContentType.objects.get_for_model(scope)
            queryset = queryset.filter(content_type=ct, object_id=scope.id)

        if 'scope_type' in request.query_params:
            scope_type_serializer = serializers.ScopeTypeSerializer(data=request.query_params)
            scope_type_serializer.is_valid(raise_exception=True)
            scope_type = scope_type_serializer.validated_data['scope_type']
            ct = ContentType.objects.get_for_model(scope_type)
            queryset = queryset.filter(content_type=ct)

        if 'opened' in request.query_params:
            queryset = queryset.filter(closed__isnull=True)

        if 'severity' in request.query_params:
            severity_codes = {v: k for k, v in models.Alert.SeverityChoices.CHOICES}
            severities = [
                severity_codes.get(severity_name) for severity_name in request.query_params.getlist('severity')]
            queryset = queryset.filter(severity__in=severities)

        if 'alert_type' in request.query_params:
            queryset = queryset.filter(alert_type__in=request.query_params.getlist('alert_type'))

        if 'acknowledged' in request.query_params:
            if request.query_params['acknowledged'] == 'False':
                queryset = queryset.filter(acknowledged=False)
            else:
                queryset = queryset.filter(acknowledged=True)

        time_search_parameters_map = {
            'closed_from': 'closed__gte',
            'closed_to': 'closed__lt',
            'created_from': 'created__gte',
            'created_to': 'created__lt',
        }

        for parameter, filter_field in time_search_parameters_map.items():
            if parameter in request.query_params:
                try:
                    queryset = queryset.filter(
                        **{filter_field: core_utils.timestamp_to_datetime(int(request.query_params[parameter]))})
                except ValueError:
                    raise ValidationError(
                        'Parameter {} is not valid. (It has to be valid timestamp)'.format(parameter))

        if ('o' in request.query_params and
                (request.query_params['o'] == 'severity' or request.query_params['o'] == '-severity')):
            queryset = queryset.order_by(request.query_params['o'])

        return queryset


class AlertViewSet(mixins.CreateModelMixin,
                   viewsets.ReadOnlyModelViewSet):

    queryset = models.Alert.objects.all()
    serializer_class = serializers.AlertSerializer
    lookup_field = 'uuid'
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (AlertFilter,)

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
            return response.Response({'detail': 'Action is already acknowledged'}, status=status.HTTP_409_CONFLICT)

        return response.Response(status=status.HTTP_200_OK)

    @decorators.detail_route(methods=['post'])
    def cancel_acknowledgment(self, request, *args, **kwargs):
        alert = self.get_object()
        if alert.acknowledged:
            alert.cancel_acknowledgment()
            return response.Response(status=status.HTTP_200_OK)
        else:
            return response.Response({'detail': 'Action is not acknowledged'}, status=status.HTTP_409_CONFLICT)
