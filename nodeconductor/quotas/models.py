from django.contrib.contenttypes import fields as ct_fields
from django.contrib.contenttypes import models as ct_models
from django.db import models, transaction
from django.db.models import Sum, F
from django.utils.encoding import python_2_unicode_compatible

from nodeconductor.logging.log import LoggableMixin
from nodeconductor.quotas import exceptions, managers
from nodeconductor.core.models import UuidMixin, NameMixin, ReversionMixin


@python_2_unicode_compatible
class Quota(UuidMixin, NameMixin, LoggableMixin, ReversionMixin, models.Model):
    """
    Abstract quota for any resource

    If quota limit is defined as -1 quota will never be exceeded
    """
    class Meta:
        unique_together = (('name', 'content_type', 'object_id'),)

    limit = models.FloatField(default=-1)
    usage = models.FloatField(default=0)

    content_type = models.ForeignKey(ct_models.ContentType)
    object_id = models.PositiveIntegerField()
    scope = ct_fields.GenericForeignKey('content_type', 'object_id')

    objects = managers.QuotaManager('scope')

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

    def __str__(self):
        return '%s quota for %s' % (self.name, self.scope)

    def get_log_fields(self):
        return ('uuid', 'name', 'limit', 'usage', 'scope')


class QuotaModelMixin(models.Model):
    """
    Add general fields and methods to model for quotas usage. Model with quotas have inherit this mixin.

    For quotas implementation such methods and fields have to be defined:
      - QUOTAS_NAMES - list of names for object quotas
      - can_user_update_quotas(self, user) - return True if user has permission to update quotas of this object
      - get_quota_parents(self) - return list of 'quota parents'

    Use such methods to change objects quotas:
      set_quota_limit, set_quota_usage, add_quota_usage.

    Other useful methods: validate_quota_change, get_sum_of_quotas_as_dict. Please check their docstrings for more details.
    """
    QUOTAS_NAMES = []  # this list has to be overridden

    class Meta:
        abstract = True

    quotas = ct_fields.GenericRelation('quotas.Quota', related_query_name='quotas')

    def set_quota_limit(self, quota_name, limit):
        # XXX: !!! Horrible hack !!! Remove ASAP !!! Propagate limits for backend quotas
        if quota_name.startswith('nc_'):
            self.quotas.filter(name=quota_name).update(limit=limit)
        else:
            self._set_editable_field_value('limit', quota_name, limit)

    def set_quota_usage(self, quota_name, usage):
        self._set_editable_field_value('usage', quota_name, usage)

    def add_quota_usage(self, quota_name, usage_delta, fail_silently=False):
        """
        Add usage_delta to current quota usage

        If <fail_silently> is True - operation will not fail if quota does not exist
        """
        self._add_delta_to_editable_field('usage', quota_name, usage_delta, fail_silently)

    def _set_editable_field_value(self, field, quota_name, value):
        with transaction.atomic():
            original_quota = self.quotas.get(name=quota_name)
            self._add_delta_to_ancestors(field, quota_name, value - getattr(original_quota, field))
            setattr(original_quota, field, value)
            original_quota.save()

    def _add_delta_to_editable_field(self, field, quota_name, delta, fail_silently=False):
        """
        Add delta to quota <field>

        If <fail_silently> is True - operation will not fail if quota does not exist
        """
        if not delta:
            return
        with transaction.atomic():
            try:
                original_quota = self.quotas.select_for_update().get(name=quota_name)
            except Quota.DoesNotExist, e:
                if not fail_silently:
                    raise e
            else:
                # Django's F() expressions makes quota.is_exceeded() unusable in signals
                # wrap update into a safe transaction instead (may not work with sqlite)
                setattr(original_quota, field, getattr(original_quota, field) + delta)
                original_quota.save(update_fields=[field])
                self._add_delta_to_ancestors(field, quota_name, delta)

    def _add_delta_to_ancestors(self, field, quota_name, delta):
        for ancestor in self._get_quota_ancestors():
            with transaction.atomic():
                try:
                    quota = ancestor.quotas.select_for_update().get(name=quota_name)
                except Quota.DoesNotExist:
                    quota = Quota.objects.create(scope=ancestor, name=quota_name)
                else:
                    setattr(quota, field, getattr(quota, field) + delta)
                    quota.save(update_fields=[field])

    def validate_quota_change(self, quota_deltas, raise_exception=False):
        """
        Get error messages about object and his ancestor quotas that will be exceeded if quota_delta will be added.

        raise_exception - if True QuotaExceededException will be raised if validation fails
        quota_deltas - dictionary of quotas deltas, example:
        {
            'ram': 1024,
            'storage': 2048,
            ...
        }
        Example of output:
            ['ram quota limit: 1024, requires: 2048(instance#1)', ...]

        """
        errors = []
        for name, delta in quota_deltas.iteritems():
            quota = self.quotas.get(name=name)
            if quota.is_exceeded(delta):
                errors.append('%s quota limit: %s, requires %s (%s)\n' % (
                    quota.name, quota.limit, quota.usage + delta, quota.scope))
        for parent in self.get_quota_parents():
            if parent.quotas.filter(name=name).exists():
                errors += parent.validate_quota_change(quota_deltas)
        if not raise_exception:
            return errors
        else:
            if errors:
                raise exceptions.QuotaExceededException('One or more quotas were exceeded: %s' % ';'.join(errors))

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
        Return list of other quota scopes that contain quotas of current scope.

        Example: Customer quotas contain quotas of all customers projects.
        """
        return []

    # XXX: This method will be improved with frontend quotas implementation.
    def can_user_update_quotas(self, user):
        """
        Return True if user has permission to update quota
        """
        return False

    @classmethod
    def get_sum_of_quotas_as_dict(cls, scopes, quota_names=None, fields=['usage', 'limit']):
        """
        Return dictionary with sum of all scopes' quotas.

        Dictionary format:
        {
            'quota_name1': 'sum of limits for quotas with such quota_name1',
            'quota_name1_usage': 'sum of usages for quotas with such quota_name1',
            ...
        }
        All `scopes` have to be instances of the same model.
        `fields` keyword argument defines sum of which fields of quotas will present in result.
        """
        if not scopes:
            return {}

        if quota_names is None:
            quota_names = cls.QUOTAS_NAMES

        scope_models = set([scope._meta.model for scope in scopes])
        if len(scope_models) > 1:
            raise exceptions.QuotaError('All scopes have to be instances of the same model')

        filter_kwargs = {
            'content_type': ct_models.ContentType.objects.get_for_model(scopes[0]),
            'object_id__in': [scope.id for scope in scopes],
            'name__in': quota_names
        }

        result = {}
        if 'usage' in fields:
            items = Quota.objects.filter(**filter_kwargs)\
                         .values('name').annotate(usage=Sum('usage'))
            for item in items:
                result[item['name'] + '_usage'] = item['usage']

        if 'limit' in fields:
            items = Quota.objects.filter(**filter_kwargs)\
                         .exclude(limit=-1).values('name').annotate(limit=Sum('limit'))
            for item in items:
                result[item['name']] = item['limit']
            for name in quota_names:
                if name not in result:
                    result[name] = -1

        return result
