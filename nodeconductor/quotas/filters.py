from __future__ import unicode_literals

import itertools

import django_filters


class QuotaFilterSetMixin(object):
    """
    Allow to order by quotas

    Usage:
        1. Add 'quotas__limit' and '-quotas__limit' to filter meta 'order_by' attribute
        if you want order by quotas limits and 'quotas__usage', '-quota__usage' if
        you want to order by quota usage.

        2. Add 'quotas__<limit or usage>__<quota_name>' to meta 'order_by' attribute if you want to
        allow user to order <quota_name>. For example 'quotas__limit__ram' will enable ordering by 'ram' quota.

    Example:
        # enable ordering by quotas "ram" and "vcpu" for MyModel

        class MyModelFilterSet(QuotaFilterMixin, django_filters.FilterSet):
            class Meta(object):
                model = models.MyModel
                order_by = [
                    'quotas__usage__ram',
                    '-quotas__usage__ram',
                    'quotas__usage__vcpu',
                    '-quotas__usage__vcpu',
                    'quotas__usage',
                    '-quotas__usage',
                ]

    Ordering can be done only by one quota at a time.
    """

    def __init__(self, data=None, queryset=None, prefix=None, strict=None):
        super(QuotaFilterSetMixin, self).__init__(data, queryset, prefix, strict)
        self._prepare_quota_ordering()

    def _prepare_quota_ordering(self):
        """ Add filtration by quota if products have to be ordered by quota """
        if not self.data or self.order_by_field not in self.data or not self.data[self.order_by_field]:
            return

        order_by = self.data[self.order_by_field]

        quotas_names = self._meta.model.QUOTAS_NAMES
        quotas_fields = ('limit', 'usage')
        ordering_prefixes = ('-', '')
        quota_filter_map = {
            '{}quotas__{}__{}'.format(prefix, field, name)
            for prefix, field, name in itertools.product(ordering_prefixes, quotas_fields, quotas_names)}

        if order_by not in quota_filter_map:
            return

        # get quota name and order_by_field from inputed data. Ex: '-quotas_usage_ram' -> ('-quotas_usage', 'ram')
        order_by_input, quota_name = order_by.rsplit('__', 1)
        # add filter by ordering quota name (ordering has to be executed only for this quotas)
        self.queryset = self.queryset.filter(quotas__name=quota_name)
        self.data[self.order_by_field] = order_by_input


class QuotaFilter(django_filters.NumberFilter):
    """
    Filter by quota value
    """

    def __init__(self, quota_name, quota_field, **kwargs):
        super(QuotaFilter, self).__init__(**kwargs)
        self.quota_name = quota_name
        self.quota_field = quota_field

    def filter(self, qs, value):
        return qs.filter(**{'quotas__name': self.quota_name, 'quotas__{}'.format(self.quota_field): value})
