from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
import django_filters
from rest_framework import filters

from nodeconductor.core import filters as core_filters
from nodeconductor.cost_tracking import models, serializers
from nodeconductor.structure import models as structure_models, SupportedServices
from nodeconductor.structure.models import Resource


class PriceEstimateFilter(django_filters.FilterSet):
    is_manually_input = django_filters.BooleanFilter()

    class Meta:
        model = models.PriceEstimate
        fields = [
            'is_manually_input',
        ]


class PriceEstimateScopeFilterBackend(core_filters.GenericKeyFilterBackend):

    def get_related_models(self):
        return models.PriceEstimate.get_estimated_models()

    def get_field_name(self):
        return 'scope'


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

        # Filter by date range
        date_range_serializer = serializers.PriceEstimateDateRangeFilterSerializer(data=request.query_params)
        date_range_serializer.is_valid(raise_exception=True)
        if 'start' in date_range_serializer.validated_data:
            year, month = date_range_serializer.validated_data['start']
            queryset = queryset.filter(Q(year__gt=year) | Q(year=year, month__gte=month))
        if 'end' in date_range_serializer.validated_data:
            year, month = date_range_serializer.validated_data['end']
            queryset = queryset.filter(Q(year__lt=year) | Q(year=year, month__lte=month))

        # Filter by customer
        if 'customer' in request.query_params:
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

            queryset = queryset.filter(qs)

        return queryset


class PriceListItemServiceFilterBackend(core_filters.GenericKeyFilterBackend):

    def get_related_models(self):
        return structure_models.Service.get_all_models()

    def get_field_name(self):
        return 'service'


class ResourceTypeFilter(django_filters.CharFilter):

    def filter(self, qs, value):
        if value:
            resource_models = SupportedServices.get_resource_models()
            try:
                model = resource_models[value]
                ct = ContentType.objects.get_for_model(model)
                return super(ResourceTypeFilter, self).filter(qs, ct)
            except (ContentType.DoesNotExist, KeyError):
                return qs.none()
        return qs


class DefaultPriceListItemFilter(django_filters.FilterSet):
    resource_content_type = core_filters.ContentTypeFilter()
    resource_type = ResourceTypeFilter(name='resource_content_type')

    class Meta:
        model = models.DefaultPriceListItem
        fields = [
            'key',
            'item_type',
            'resource_content_type',
            'resource_type',
        ]
