from __future__ import unicode_literals

from rest_framework import serializers

from nodeconductor.core.serializers import GenericRelatedField
from nodeconductor.cost_tracking import models


class PriceEstimateSerializer(serializers.HyperlinkedModelSerializer):
    scope = GenericRelatedField(related_models=models.PriceEstimate.get_editable_estimated_models())

    class Meta(object):
        model = models.PriceEstimate
        fields = ('url', 'uuid', 'scope', 'total', 'details', 'month', 'year', 'is_manually_inputed')
        read_only_fields = ('is_manually_inputed',)
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def validate(self, data):
        if self.instance is None and models.PriceEstimate.objects.filter(
                scope=data['scope'], year=data['year'], month=data['month'], is_manually_inputed=True).exists():
            raise serializers.ValidationError(
                'Estimate for given month already exists. Use PATCH request to update it.')
        return data

    # TODO: redo this validation - mark fields as read_only on update
    def validate_scope(self, value):
        if self.instance is not None and self.instance.scope != value:
            raise serializers.ValidationError('Field scope can not be updated.')
        return value

    def validate_month(self, value):
        if self.instance is not None and self.instance.month != value:
            raise serializers.ValidationError('Field month can not be updated.')
        return value

    def validate_year(self, value):
        if self.instance is not None and self.instance.year != value:
            raise serializers.ValidationError('Field month can not be updated.')
        return value

    def create(self, validated_data):
        validated_data['is_manually_inputed'] = True
        price_estimate = super(PriceEstimateSerializer, self).create(validated_data)
        return price_estimate


class YearMonthField(serializers.CharField):
    """ Field that support year-month representation in format YYYY.MM """

    def to_internal_value(self, value):
        try:
            year, month = [int(el) for el in value.split('.')]
        except ValueError:
            raise serializers.ValidationError('Value "{}" should be valid be in format YYYY.MM'.format(value))
        return year, month


class PriceEstimateDateFilterSerializer(serializers.Serializer):
    date_list = serializers.ListField(
        child=YearMonthField(),
        required=False
    )


class PriceEstimateDateRangeFilterSerializer(serializers.Serializer):
    start = YearMonthField(required=False)
    end = YearMonthField(required=False)
