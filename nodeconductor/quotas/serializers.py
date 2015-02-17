from rest_framework import serializers

from nodeconductor.quotas import models, utils
from nodeconductor.core.serializers import GenericRelatedField


class QuotaSerializer(serializers.HyperlinkedModelSerializer):
    scope = GenericRelatedField(related_models=utils.get_models_with_quotas(), read_only=True)

    class Meta(object):
        model = models.Quota
        fields = ('url', 'uuid', 'name', 'limit', 'usage', 'scope')
        read_only_fields = ('uuid', 'name', 'usage')
        lookup_field = 'uuid'

    # TODO: cleanup after migration to drf 3
    def validate(self, attrs):
        from nodeconductor.structure.serializers import fix_non_nullable_attrs
        return fix_non_nullable_attrs(attrs)
