from django.contrib.contenttypes import fields as ct_fields
from django.contrib.contenttypes import models as ct_models
from django.db import models
from django.db.models import Sum

from nodeconductor.quotas import exceptions, managers
from nodeconductor.core.models import UuidMixin


class Quota(UuidMixin, models.Model):
    """
    Abstract quota for any resource

    If quota limit is defined as -1 quota will never be exceeded
    """
    class Meta:
        unique_together = (('name', 'content_type', 'object_id'),)

    name = models.CharField(max_length=31)
    limit = models.FloatField(default=-1)
    usage = models.FloatField(default=0)

    content_type = models.ForeignKey(ct_models.ContentType)
    object_id = models.PositiveIntegerField()
    owner = ct_fields.GenericForeignKey('content_type', 'object_id')

    objects = managers.QuotaManager()

    def is_exceeded(self, delta=None, threshold=None):
        """
        Check is quota exceeded

        If delta is not None then checks if quota exceeds with additional delta usage
        If threshold is not None then checks if quota usage over threshold * limit
        """
        if self.limit == -1:
            return False

        usage = self.usage
        limit = self.limit

        if delta is not None:
            usage += delta
        if threshold is not None:
            limit = threshold * limit

        return usage > limit


class QuotaModelMixin(models.Model):
    """
    Add general fields and methods to model for quotas usage. Model with quotas have inherit this mixin.

    For quotas implementation such methods and fields have to be defined:
      - QUOTAS_NAMES - list of names for object quotas
      - can_user_update_quotas(self, user) - return True if user has permission to update quotas of this object
      - get_quota_parents(self) - return list of 'quota parents'

    Use such methods to change objects quotas:
      set_quota_limit, set_quota_usage, change_quota_usage.

    Other useful methods: get_quota_errors, get_sum_of_quotas_as_dict. Please check their docstrings for more details.
    """
    QUOTAS_NAMES = []  # this list has to be overridden

    class Meta:
        abstract = True

    quotas = ct_fields.GenericRelation('quotas.Quota', related_query_name='quotas')

    def set_quota_limit(self, quota_name, limit):
        self.quotas.filter(name=quota_name).update(limit=limit)

    def set_quota_usage(self, quota_name, usage):
        original_quota = self.quotas.get(name=quota_name)
        self._add_usage_to_ancestors(quota_name, usage - original_quota.usage)
        original_quota.usage = usage
        original_quota.save()

    def change_quota_usage(self, quota_name, usage_delta):
        """
        Add to usage_delta to current quota usage
        """
        original_quota = self.quotas.get(name=quota_name)
        original_quota.usage += usage_delta
        original_quota.save()
        self._add_usage_to_ancestors(quota_name, usage_delta)

    def _add_usage_to_ancestors(self, quota_name, usage):
        for ancestor in self._get_quota_ancestors():
            try:
                quota = ancestor.quotas.get(name=quota_name)
                quota.usage += usage
                quota.save()
            except Quota.DoesNotExist:
                # we do not do anything if ancestor does not have such quota
                pass

    def get_quota_errors(self, quota_deltas):
        """
        Get error messages about object and his ancestor quotas that will be exceeded if quota_delta will be added

        quota_deltas - dictionary of quotas deltas, example:
        {
            'ram': 1024,
            'storage': 2048,
            ...
        }
        Example of error message:
        """
        errors = []
        for name, delta in quota_deltas.iteritems():
            quota = self.quotas.get(name=name)
            if quota.is_exceeded(delta):
                errors.append('%s quota limit: %s, requires %s (%s)\n' % (
                    quota.name, quota.limit, quota.usage + delta, quota.owner))
        for parent in self.get_quota_parents():
            errors += parent.get_quota_errors(quota_deltas)
        return errors

    def _get_quota_ancestors(self):
        """
        Get all unique quota ancestors
        """
        ancestors = list(self.get_quota_parents())
        ancestor_unique_attributes = [(a.__class__, a.id) for a in ancestors]
        for ancestor in ancestors:
            for parent in ancestor.get_quota_parents():
                if (parent.__class__, parent.id) not in ancestor_unique_attributes:
                    ancestors.append(parent)
        return ancestors

    def get_quota_parents(self):
        """
        Return list of other quota owners that contain quotas of current owner.

        Example: Customer quotas contain quotas of all customers projects.
        """
        return []

    def can_user_update_quotas(self, user):
        """
        Return True if user has permission to update quota
        """
        raise NotImplementedError('This method have to be defined for each quota owner separately')

    @classmethod
    def get_sum_of_quotas_as_dict(cls, owners, quota_names=None, fields=['usage', 'limit']):
        """
        Return dictionary with sum of all owners quotas.

        Dictionary format:
        {
            'quota_name1': 'sum of limits for quotas with such quota_name1',
            'quota_name1_usage': 'sum of usages for quotas with such quota_name1',
            ...
        }
        All `owners` have to be instances of the same model.
        `fields` keyword argument defines sum of which fields of quotas will present in result.
        """
        if quota_names is None:
            quota_names = cls.QUOTAS_NAMES

        owner_models = set([owner._meta.model for owner in owners])
        if len(owner_models) > 1:
            raise exceptions.QuotaError('All owners have to be instances of the same model')

        annotate_kwars = dict((field, Sum(field)) for field in fields)
        filter_kwargs = {
            'content_type': ct_models.ContentType.objects.get_for_model(owners[0]),
            'object_id__in': [owner.id for owner in owners],
            'name__in': quota_names
        }

        quota_sums = Quota.objects.filter(**filter_kwargs).values('name').annotate(**annotate_kwars)

        result = {}
        if 'usage' in fields:
            for quota_sum in quota_sums:
                result[quota_sum['name'] + '_usage'] = quota_sum['usage']

        if 'limit' in fields:
            for quota_sum in quota_sums:
                result[quota_sum['name']] = quota_sum['limit']

        return result
