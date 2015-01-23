from django.contrib.contenttypes import fields as ct_fields
from django.contrib.contenttypes import generic as ct_generic
from django.contrib.contenttypes import models as ct_models
from django.db import models


class Quota(models.Model):
    """
    Abstract quota for any resource
    """
    name = models.CharField(max_length=31)
    limit = models.FloatField(default=0)
    usage = models.FloatField(default=0)

    content_type = models.ForeignKey(ct_models.ContentType)
    object_id = models.PositiveIntegerField()
    owner = ct_fields.GenericForeignKey('content_type', 'object_id')


class QuotaModelMixin(object):
    """
    Add general fields and methods to model for quotas usage
    """
    quotas = ct_generic.GenericRelation(Quota)

    def change_quota_usage(self, quota_name, usage_delta):
        """
        Add to usage_delta to current quota usage
        """
        quota = self.quotas.get(name=quota_name)
        quota.usage += usage_delta
        quota.save()

    def is_quota_limit_exceeded(self, quota_name, usage_delta):
        quota = self.quotas.get(name=quota_name)
        return quota.usage + usage_delta > quota.limit
