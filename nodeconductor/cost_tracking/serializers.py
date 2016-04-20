from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.utils import six
from rest_framework import serializers

from nodeconductor.core.serializers import GenericRelatedField, AugmentedSerializerMixin, JSONField
from nodeconductor.core.signals import pre_serializer_fields
from nodeconductor.cost_tracking import models
from nodeconductor.structure import SupportedServices, models as structure_models
from nodeconductor.structure.filters import ScopeTypeFilterBackend
from nodeconductor.structure.serializers import ProjectSerializer, BaseResourceSerializer


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
        return ScopeTypeFilterBackend.get_scope_type(obj) or obj.details.get('scope_type')

    def get_resource_type(self, obj):
        if not obj.is_leaf:
            return None
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


class PriceListItemSerializer(serializers.HyperlinkedModelSerializer):
    service = GenericRelatedField(related_models=structure_models.Service.get_all_models())

    class Meta:
        model = models.PriceListItem
        fields = ('url', 'uuid', 'key', 'item_type', 'value', 'units', 'service')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def create(self, validated_data):
        # XXX: This behavior is wrong for services with several resources, find a better approach
        resource_class = SupportedServices.get_related_models(validated_data['service'])['resources'][0]
        validated_data['resource_content_type'] = ContentType.objects.get_for_model(resource_class)
        return super(PriceListItemSerializer, self).create(validated_data)


class DefaultPriceListItemSerializer(serializers.HyperlinkedModelSerializer):

    resource_type = serializers.SerializerMethodField()
    value = serializers.FloatField()
    metadata = JSONField()

    class Meta:
        model = models.DefaultPriceListItem
        fields = ('url', 'uuid', 'key', 'item_type', 'value', 'resource_type', 'metadata')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def get_resource_type(self, obj):
        return SupportedServices.get_name_for_model(obj.resource_content_type.model_class())


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
