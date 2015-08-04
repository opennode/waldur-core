from __future__ import unicode_literals

import re

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
import django_filters
from rest_framework import viewsets, permissions, exceptions, filters, mixins

from nodeconductor.core import filters as core_filters, serializers as core_serializers
from nodeconductor.cost_tracking import models, serializers
from nodeconductor.structure import models as structure_models


# XXX: this function is same for logging and cost_tracking - it can be moved to core utils
def _convert(name):
    """ Converts CamelCase to underscore """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class PriceEstimateFilter(django_filters.FilterSet):
    scope = core_filters.GenericKeyFilter(related_models=models.PriceEstimate.get_estimated_models())
    is_manually_input = django_filters.BooleanFilter()

    class Meta:
        model = models.PriceEstimate
        fields = [
            'scope',
            'is_manually_input',
        ]


class PriceEstimateCustomerFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        if 'customer' not in request.query_params:
            return queryset

        customer_uuid = request.query_params['customer']
        qs = Q()
        for model in models.PriceEstimate.get_estimated_models():
            content_type = ContentType.objects.get_for_model(model)
            if model == structure_models.Customer:
                query = {'uuid': customer_uuid}
            else:
                query = {model.Permissions.customer_path + '__uuid': customer_uuid}
            ids = model.objects.filter(**query).values_list('pk', flat=True)
            qs |= Q(content_type=content_type, object_id__in=ids)

        return queryset.filter(qs)


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


class PriceEditPermissionMixin(object):

    def can_user_modify_price_object(self, scope):
        if self.request.user.is_staff:
            return True
        customer = reduce(getattr, scope.Permissions.customer_path.split('__'), scope)
        if customer.has_user(self.request.user, structure_models.CustomerRole.OWNER):
            return True
        return False


class PriceEstimateViewSet(PriceEditPermissionMixin, viewsets.ModelViewSet):
    queryset = models.PriceEstimate.objects.all()
    serializer_class = serializers.PriceEstimateSerializer
    lookup_field = 'uuid'
    filter_backends = (
        filters.DjangoFilterBackend,
        AdditionalPriceEstimateFilterBackend,
        PriceEstimateCustomerFilter
    )
    filter_class = PriceEstimateFilter
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return models.PriceEstimate.objects.filtered_for_user(self.request.user).filter(is_visible=True).order_by(
            '-year', '-month')

    def perform_create(self, serializer):
        if not self.can_user_modify_price_object(serializer.validated_data['scope']):
            raise exceptions.PermissionDenied('You do not have permission to perform this action.')

        super(PriceEstimateViewSet, self).perform_create(serializer)

    def initial(self, request, *args, **kwargs):
        if self.action in ('partial_update', 'destroy', 'update'):
            price_estimate = self.get_object()
            if not price_estimate.is_manually_input:
                raise exceptions.MethodNotAllowed('Auto calculated price estimate can not be edited or deleted')
            if not self.can_user_modify_price_object(price_estimate.scope):
                raise exceptions.PermissionDenied('You do not have permission to perform this action.')

        return super(PriceEstimateViewSet, self).initial(request, *args, **kwargs)


class ResourceFilter(django_filters.CharFilter):
    """ Filter by price list items for concrete resource. """

    def filter(self, qs, value):
        if value:
            field = core_serializers.GenericRelatedField(related_models=structure_models.Resource.get_all_models())
            resource = field.to_internal_value(value)
            ct = ContentType.objects.get_for_model(resource)
            resource_price_items_ids = models.ResourcePriceItem.objects.filter(
                object_id=resource.id, content_type=ct).values_list('id', flat=True)
            return qs.filter(resource_price_items__in=resource_price_items_ids)
        return qs


class PriceListItemFilter(django_filters.FilterSet):
    service = core_filters.GenericKeyFilter(related_models=structure_models.Service.get_all_models())
    resource = ResourceFilter()

    class Meta:
        model = models.PriceListItem
        fields = [
            'service',
            'resource',
        ]


class PriceListItemViewSet(PriceEditPermissionMixin,
                           mixins.UpdateModelMixin,
                           viewsets.ReadOnlyModelViewSet):
    queryset = models.PriceListItem.objects.all()
    serializer_class = serializers.PriceListItemSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = PriceListItemFilter
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return models.PriceListItem.objects.filtered_for_user(self.request.user)

    def initial(self, request, *args, **kwargs):
        if self.action in ('partial_update', 'update'):
            price_list_item = self.get_object()
            if not self.can_user_modify_price_object(price_list_item.service):
                raise exceptions.PermissionDenied('You do not have permission to perform this action.')

        return super(PriceListItemViewSet, self).initial(request, *args, **kwargs)
