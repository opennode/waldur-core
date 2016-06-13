from __future__ import unicode_literals

from django.db import IntegrityError
from django.utils import six
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.reverse import reverse

from nodeconductor.core.serializers import GenericRelatedField, AugmentedSerializerMixin, JSONField
from nodeconductor.core.signals import pre_serializer_fields
from nodeconductor.cost_tracking import models
from nodeconductor.structure import SupportedServices, models as structure_models
from nodeconductor.structure.filters import ScopeTypeFilterBackend
from nodeconductor.structure.serializers import ProjectSerializer


class PriceEstimateSerializer(AugmentedSerializerMixin, serializers.HyperlinkedModelSerializer):
    scope = GenericRelatedField(related_models=models.PriceEstimate.get_editable_estimated_models())
    scope_name = serializers.SerializerMethodField()
    scope_type = serializers.SerializerMethodField()
    resource_type = serializers.SerializerMethodField()

    class Meta(object):
        model = models.PriceEstimate
        fields = ('url', 'uuid', 'scope', 'total', 'consumed', 'month', 'year',
                  'is_manually_input', 'scope_name', 'scope_type', 'resource_type', 'threshold')
        read_only_fields = ('is_manually_input', 'threshold')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }
        protected_fields = ('scope', 'year', 'month')

    def validate(self, data):
        if self.instance is None and models.PriceEstimate.objects.filter(
                scope=data['scope'], year=data['year'], month=data['month'], is_manually_input=True).exists():
            raise serializers.ValidationError(
                'Estimate for given month already exists. Use PATCH request to update it.')
        return data

    def create(self, validated_data):
        validated_data['is_manually_input'] = True
        price_estimate = super(PriceEstimateSerializer, self).create(validated_data)
        return price_estimate

    def get_scope_name(self, obj):
        return six.text_type(obj.scope or obj.details.get('scope_name'))  # respect to unicode

    def get_scope_type(self, obj):
        return ScopeTypeFilterBackend.get_scope_type(obj.content_type.model_class())

    def get_resource_type(self, obj):
        if self.get_scope_type(obj) == 'resource':
            return SupportedServices.get_name_for_model(obj.content_type.model_class())


class YearMonthField(serializers.CharField):
    """ Field that support year-month representation in format YYYY.MM """

    def to_internal_value(self, value):
        try:
            year, month = [int(el) for el in value.split('.')]
        except ValueError:
            raise serializers.ValidationError('Value "{}" should be valid be in format YYYY.MM'.format(value))
        if not 0 < month < 13:
            raise serializers.ValidationError('Month has to be from 1 to 12')
        return year, month


class PriceEstimateDateFilterSerializer(serializers.Serializer):
    date_list = serializers.ListField(
        child=YearMonthField(),
        required=False
    )


class PriceEstimateDateRangeFilterSerializer(serializers.Serializer):
    start = YearMonthField(required=False)
    end = YearMonthField(required=False)

    def validate(self, data):
        if 'start' in data and 'end' in data and data['start'] >= data['end']:
            raise serializers.ValidationError('Start has to be earlier than end.')
        return data


class PriceListItemSerializer(AugmentedSerializerMixin,
                              serializers.HyperlinkedModelSerializer):
    service = GenericRelatedField(related_models=structure_models.Service.get_all_models())
    default_price_list_item = serializers.HyperlinkedRelatedField(
        view_name='defaultpricelistitem-detail',
        lookup_field='uuid',
        queryset=models.DefaultPriceListItem.objects.all().select_related('resource_content_type'))

    class Meta:
        model = models.PriceListItem
        fields = ('url', 'uuid', 'units', 'value', 'service', 'default_price_list_item')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
            'default_price_list_item': {'lookup_field': 'uuid'}
        }
        protected_fields = ('service', 'default_price_list_item')

    def create(self, validated_data):
        try:
            return super(PriceListItemSerializer, self).create(validated_data)
        except IntegrityError:
            raise ValidationError('Price list item for service already exists')


class DefaultPriceListItemSerializer(serializers.HyperlinkedModelSerializer):
    value = serializers.FloatField()
    metadata = JSONField()

    class Meta:
        model = models.DefaultPriceListItem
        fields = ('url', 'uuid', 'key', 'item_type', 'value', 'resource_type', 'metadata')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


class MergedPriceListItemSerializer(serializers.HyperlinkedModelSerializer):
    value = serializers.SerializerMethodField()
    units = serializers.SerializerMethodField()
    is_manually_input = serializers.SerializerMethodField()
    service_price_list_item_url = serializers.SerializerMethodField()
    metadata = JSONField()

    class Meta:
        model = models.DefaultPriceListItem
        fields = ('url', 'uuid', 'key', 'item_type', 'units', 'value',
                  'resource_type', 'metadata', 'is_manually_input', 'service_price_list_item_url')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def get_value(self, obj):
        return getattr(obj, 'service_item', None) and float(obj.service_item[0].value) or float(obj.value)

    def get_units(self, obj):
        return getattr(obj, 'service_item', None) and obj.service_item[0].units or obj.units

    def get_is_manually_input(self, obj):
        return bool(getattr(obj, 'service_item', None))

    def get_service_price_list_item_url(self, obj):
        if not getattr(obj, 'service_item', None):
            return
        return reverse('pricelistitem-detail',
                       kwargs={'uuid': obj.service_item[0].uuid.hex},
                       request=self.context['request'])


class PriceEstimateThresholdSerializer(serializers.Serializer):
    threshold = serializers.FloatField(min_value=0, required=True)
    scope = GenericRelatedField(related_models=models.PriceEstimate.get_estimated_models(), required=True)


class PriceEstimateLimitSerializer(serializers.Serializer):
    limit = serializers.FloatField(required=True)
    scope = GenericRelatedField(related_models=models.PriceEstimate.get_estimated_models(), required=True)


class NestedPriceEstimateSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = models.PriceEstimate
        fields = ('threshold', 'total', 'limit')


def get_price_estimate_for_project(serializer, project):
    try:
        estimate = models.PriceEstimate.objects.get_current(project)
    except models.PriceEstimate.DoesNotExist:
        return {
            'threshold': 0.0,
            'total': 0.0,
            'limit': -1.0
        }
    else:
        serializer = NestedPriceEstimateSerializer(instance=estimate, context=serializer.context)
        return serializer.data


def add_price_estimate_for_project(sender, fields, **kwargs):
    fields['price_estimate'] = serializers.SerializerMethodField()
    setattr(sender, 'get_price_estimate', get_price_estimate_for_project)


pre_serializer_fields.connect(add_price_estimate_for_project, sender=ProjectSerializer)
