import inspect

from django.contrib.contenttypes import fields as ct_fields
from django.contrib.contenttypes import models as ct_models
from django.db import models, transaction
from django.db.models import Sum
from django.utils import six
from django.utils.encoding import python_2_unicode_compatible
from model_utils import FieldTracker

from nodeconductor.logging.log import LoggableMixin
from nodeconductor.quotas import exceptions, managers, fields
from nodeconductor.core.models import UuidMixin, ReversionMixin, DescendantMixin


@python_2_unicode_compatible
class Quota(UuidMixin, LoggableMixin, ReversionMixin, models.Model):
    """
    Abstract quota for any resource.

    Quota can exist without scope - for example quota for all projects or all customers on site
    If quota limit is defined as -1 quota will never be exceeded
    """
    class Meta:
        unique_together = (('name', 'content_type', 'object_id'),)

    limit = models.FloatField(default=-1)
    usage = models.FloatField(default=0)
    name = models.CharField(max_length=150, db_index=True)

    content_type = models.ForeignKey(ct_models.ContentType, null=True)
    object_id = models.PositiveIntegerField(null=True)
    scope = ct_fields.GenericForeignKey('content_type', 'object_id')

    objects = managers.QuotaManager('scope')
    tracker = FieldTracker()

    def __str__(self):
        return '%s quota for %s' % (self.name, self.scope)

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

    def get_log_fields(self):
        return ('uuid', 'name', 'limit', 'usage', 'scope')

    def get_field(self):
        fields = self.scope.get_quotas_fields()
        try:
            return next(f for f in fields if f.name == self.name)
        except StopIteration:
            return


class QuotaModelMixin(models.Model):
    """
    Add general fields and methods to model for quotas usage.

    Model with quotas have inherit this mixin.
    For quotas implementation such methods and fields have to be defined:
      - class Quota(QuotaModelMixin) - class with quotas fields as attributes.
      - can_user_update_quotas(self, user) - Return True if user has permission to update quotas of this object.
      - QUOTAS_NAMES - List of names for object quotas. Deprecated, define quotas as fields in Quotas class instead.
      - GLOBAL_COUNT_QUOTA_NAME - Name of global count quota. It presents - global quota will be automatically created
                                  for model. Optional attribute.

    Example:
        Customer(models.Model):
            ...
            Quotas(quotas_models.QuotaModelMixin.Quotas):
                nc_user_count = quotas_fields.QuotaField()  # define user count quota for customers

            def can_user_update_quotas(self, user):
                # only staff user can edit Customer quotas
                return user.is_staff

    Use such methods to change objects quotas:
      set_quota_limit, set_quota_usage, add_quota_usage.

    Helper methods validate_quota_change and get_sum_of_quotas_as_dict provide common operations with objects quotas.
    Check methods docstrings for more details.
    """
    QUOTAS_NAMES = []  # this list has to be overridden. Deprecated use class Quotas instead

    class Quotas(six.with_metaclass(fields.FieldsContainerMeta)):
        pass  # register model quota fields here

    class Meta:
        abstract = True

    quotas = ct_fields.GenericRelation('quotas.Quota', related_query_name='quotas')

    def get_quota_usage(self, quota_name, default=0):
        """
        Get quota usage by quota_name if it exists or return default value.
        """
        if quota_name not in self.Quotas.__dict__:
            raise ValueError('Invalid quota name {}'.format(quota_name))
        try:
            return self.quotas.get(name=quota_name).usage
        except Quota.DoesNotExist:
            return default

    def set_quota_limit(self, quota_name, limit):
        self.quotas.filter(name=quota_name).update(limit=limit)

    def set_quota_usage(self, quota_name, usage, fail_silently=False):
        with transaction.atomic():
            try:
                original_quota = self.quotas.get(name=quota_name)
            except Quota.DoesNotExist:
                if not fail_silently:
                    raise
            else:
                self._add_delta_to_ancestors('usage', quota_name, usage - original_quota.usage)
                original_quota.usage = usage
                original_quota.save(update_fields=['usage'])

    def add_quota_usage(self, quota_name, usage_delta, fail_silently=False):
        """
        Add usage_delta to current quota usage

        If <fail_silently> is True - operation will not fail if quota does not exist
        """
        self._add_delta_to_editable_field('usage', quota_name, usage_delta, fail_silently)

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
                old_value = getattr(original_quota, field)
                # make sure that quota usage is not lower then 0 - it can become lower on cascade deletion
                new_value = max(old_value + delta, 0)
                delta = new_value - old_value
                setattr(original_quota, field, new_value)
                original_quota.save(update_fields=[field])
                self._add_delta_to_ancestors(field, quota_name, delta)

    def _add_delta_to_ancestors(self, field, quota_name, delta):
        if not delta or not isinstance(self, DescendantMixin):
            return

        ancestors = (a for a in self.get_ancestors() if isinstance(a, QuotaModelMixin))
        for ancestor in ancestors:
            with transaction.atomic():
                try:
                    quota = ancestor.quotas.select_for_update().get(name=quota_name)
                except Quota.DoesNotExist:
                    # ignore quotas change if parent does not have such quota
                    pass
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
        if isinstance(self, DescendantMixin):
            for parent in self.get_parents():
                if isinstance(parent, QuotaModelMixin) and parent.quotas.filter(name=name).exists():
                    errors += parent.validate_quota_change(quota_deltas)
        if not raise_exception:
            return errors
        else:
            if errors:
                raise exceptions.QuotaExceededException('One or more quotas were exceeded: %s' % ';'.join(errors))

    def can_user_update_quotas(self, user):
        """
        Return True if user has permission to update quota
        """
        return user.is_staff

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

    @classmethod
    def get_quotas_fields(cls, field_class=None):
        if not hasattr(cls, '_quota_fields'):
            cls._quota_fields = dict(inspect.getmembers(cls.Quotas, lambda m: isinstance(m, fields.QuotaField))).values()
        if field_class is not None:
            return [v for v in cls._quota_fields if isinstance(v, field_class)]
        return cls._quota_fields
