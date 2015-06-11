from rest_framework import serializers

from nodeconductor.quotas import models, utils
from nodeconductor.core.serializers import GenericRelatedField

import logging

logger = logging.getLogger(__name__)

class QuotaSerializer(serializers.HyperlinkedModelSerializer):
    scope = GenericRelatedField(related_models=utils.get_models_with_quotas(), read_only=True)

    class Meta(object):
        model = models.Quota
        fields = ('url', 'uuid', 'name', 'limit', 'usage', 'scope')
        read_only_fields = ('uuid', 'name', 'usage')
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

