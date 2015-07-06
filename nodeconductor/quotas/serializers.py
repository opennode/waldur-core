from rest_framework import serializers

from nodeconductor.quotas import models, utils
from nodeconductor.core.fields import TimestampField
from nodeconductor.core.serializers import GenericRelatedField


class QuotaSerializer(serializers.HyperlinkedModelSerializer):
    scope = GenericRelatedField(related_models=utils.get_models_with_quotas(), read_only=True)

    class Meta(object):
        model = models.Quota
        fields = ('url', 'uuid', 'name', 'limit', 'usage', 'scope')
        read_only_fields = ('uuid', 'name', 'usage')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }


# XXX: If we will create history for any other endpoint - this serializer has to be moved to core.
class HistorySerializer(serializers.Serializer):
    """
    Receive datetime as timestamps and converts them to list of datetimes

    Support 2 types of input data:
     - start, end and points_count - interval from <start> to <end> will be automatically splitted to
                                     <points_count> pieces
     - point_list - list of timestamps that will be converted to datetime points

    """
    start = TimestampField(required=False)
    end = TimestampField(required=False)
    points_count = serializers.IntegerField(min_value=2, required=False)
    point_list = serializers.ListField(
        child=TimestampField(),
        required=False
    )

    def validate(self, attrs):
        autosplit_fields = {'start', 'end', 'points_count'}
        if ('point_list' not in attrs or not attrs['point_list']) and not autosplit_fields == set(attrs.keys()):
            raise serializers.ValidationError(
                'Not enough parameters for historical data. '
                '("point_list" or "start" + "end" + "points_count" parameters has to be provided)')
        if 'point_list' in attrs and autosplit_fields & set(attrs.keys()):
            raise serializers.ValidationError(
                'To much parameters for historical data. '
                '("point_list" or "start" + "end" + "points_count" parameters has to be provided)')
        if 'point_list' not in attrs and not attrs['start'] < attrs['end']:
            raise serializers.ValidationError('start timestamps has to be greater then end')
        return attrs

    # History serializer is used for validation only. To avoid confuses with to_internal_value or to_representation
    # implementations - lets provide custom method for such serializers.
    def get_filter_data(self):
        if 'point_list' in self.validated_data:
            return self.validated_data['point_list']
        else:
            interval = ((self.validated_data['end'] - self.validated_data['start']) /
                        (self.validated_data['points_count'] - 1))
            return [self.validated_data['start'] + interval * i for i in range(self.validated_data['points_count'])]
