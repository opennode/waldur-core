from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from model_utils.fields import AutoLastModifiedField

from nodeconductor.core.models import NameMixin


class MonitoringItem(NameMixin, models.Model):
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    scope = GenericForeignKey('content_type', 'object_id')

    value = models.NullBooleanField()
    last_updated = AutoLastModifiedField()

    class Meta:
        unique_together = ('name', 'content_type', 'object_id')


class MonitoringModelMixin(models.Model):
    class Meta:
        abstract = True

    monitoring_items = GenericRelation('monitoring.MonitoringItem',
                                       related_query_name='monitoring_items')
