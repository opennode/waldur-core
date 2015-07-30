from __future__ import unicode_literals

import re

from django.db.models import Q
import django_filters
from rest_framework import viewsets, permissions, exceptions, filters

from nodeconductor.core import filters as core_filters
from nodeconductor.cost_tracking import models, serializers
from nodeconductor.structure import models as structure_models


# XXX: this function is same for logging and cost_tracking - it can be moved to core utils
def _convert(name):
    """ Converts CamelCase to underscore """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class PriceEstimateFilter(django_filters.FilterSet):
    scope = core_filters.GenericKeyFilter(related_models=models.PriceEstimate.get_estimated_models())
    is_manually_inputed = django_filters.BooleanFilter()

    class Meta:
        model = models.PriceEstimate
        fields = [
            'scope',
            'is_manually_inputed',
        ]


class AdditionalPriceEstimateFilterBackend(filters.BaseFilterBackend):

    def filter_queryset(self, request, queryset, view):
        if 'date' in request.query_params:
            date_serializer = serializers.PriceEstimateDateFilterSerializer(
                data={'date_list': request.query_params.getlist('date')})
            date_serializer.is_valid(raise_exception=True)
            query = Q()
            for year, month in date_serializer.validated_data['date_list']:
                query |= Q(year=year, month=month)
            queryset = queryset.filter(query)

        date_range_serializer = serializers.PriceEstimateDateRangeFilterSerializer(data=request.query_params)
        date_range_serializer.is_valid(raise_exception=True)
        if 'start' in date_range_serializer.validated_data:
            year, month = date_range_serializer.validated_data['start']
            queryset = queryset.filter(Q(year__gt=year) | Q(year=year, month__gte=month))
        if 'end' in date_range_serializer.validated_data:
            year, month = date_range_serializer.validated_data['end']
            queryset = queryset.filter(Q(year__lt=year) | Q(year=year, month__lte=month))
        return queryset


class PriceEstimateViewSet(viewsets.ModelViewSet):
    queryset = models.PriceEstimate.objects.all()
    serializer_class = serializers.PriceEstimateSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.DjangoFilterBackend, AdditionalPriceEstimateFilterBackend)
    filter_class = PriceEstimateFilter
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return models.PriceEstimate.objects.filtered_for_user(self.request.user).filter(is_visible=True).order_by(
            '-year', '-month')

    def can_user_modify_price_estimate(self, scope):
        if self.request.user.is_staff:
            return True
        customer = reduce(getattr, scope.Permissions.customer_path.split('__'), scope)
        if customer.has_user(self.request.user, structure_models.CustomerRole.OWNER):
            return True
        return False

    def perform_create(self, serializer):
        if not self.can_user_modify_price_estimate(serializer.validated_data['scope']):
            raise exceptions.PermissionDenied('You do not have permission to perform this action.')

        super(PriceEstimateViewSet, self).perform_create(serializer)

    def initial(self, request, *args, **kwargs):
        if self.action in ('partial_update', 'destroy'):
            price_estimate = self.get_object()
            if not price_estimate.is_manually_inputed:
                raise exceptions.MethodNotAllowed('Auto calculated price estimate can not be edited or deleted')
            if not self.can_user_modify_price_estimate(price_estimate.scope):
                raise exceptions.PermissionDenied('You do not have permission to perform this action.')

        return super(PriceEstimateViewSet, self).initial(request, *args, **kwargs)


class PriceListFilter(django_filters.FilterSet):
    service = core_filters.GenericKeyFilter(related_models=structure_models.Service.get_all_models())

    class Meta:
        model = models.PriceList
        fields = [
            'service',
        ]


class PriceListViewSet(viewsets.ModelViewSet):
    queryset = models.PriceList.objects.all().select_related('items')
    serializer_class = serializers.PriceListSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = PriceListFilter
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return models.PriceList.objects.filtered_for_user(self.request.user).select_related('items')

    def can_user_modify_price_list(self, service):
        if self.request.user.is_staff:
            return True
        customer = reduce(getattr, service.Permissions.customer_path.split('__'), service)
        if customer.has_user(self.request.user, structure_models.CustomerRole.OWNER):
            return True
        return False

    def initial(self, request, *args, **kwargs):
        if self.action in ('partial_update', 'destroy'):
            price_estimate = self.get_object()
            if not self.can_user_modify_price_list(price_estimate.service):
                raise exceptions.PermissionDenied('You do not have permission to perform this action.')

        return super(PriceListViewSet, self).initial(request, *args, **kwargs)

    def perform_create(self, serializer):
        if not self.can_user_modify_price_list(serializer.validated_data['service']):
            raise exceptions.PermissionDenied('You do not have permission to perform this action.')

        super(PriceListViewSet, self).perform_create(serializer)
