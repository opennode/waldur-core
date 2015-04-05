from __future__ import unicode_literals

from rest_framework import permissions as rf_permissions, exceptions as rf_exceptions
from rest_framework import mixins
from rest_framework import viewsets

from nodeconductor.quotas import models, serializers


class QuotaViewSet(mixins.UpdateModelMixin,
                   viewsets.ReadOnlyModelViewSet):

    queryset = models.Quota.objects.all()
    serializer_class = serializers.QuotaSerializer
    lookup_field = 'uuid'
    permission_classes = (rf_permissions.IsAuthenticated,)
    pagination_class = None

    def get_queryset(self):
        return models.Quota.objects.filtered_for_user(self.request.user)

    def perform_update(self, serializer):
        if not serializer.instance.scope.can_user_update_quotas(self.request.user):
            raise rf_exceptions.PermissionDenied('You do not have permission to perform this action.')

        super(QuotaViewSet, self).perform_update(serializer)


class QuotaFilterMixin(object):
    """
    Allow to order by quotas

    Usage:
    1. Add 'quotas__limit' and '-quotas__limit' to filter meta 'order_by' attribute
    if you want order by quotas limits and 'quotas__usage', '-quota__usage' if
    you want to order by quota usage.

    2. Add 'quotas__<limit or usage>__<quota_name>' to meta 'order_by' attribute if you want to
    allow user to order <quota_name>. For example 'quotas__limit__ram' will enable ordering by 'ram' quota.

    Ordering can be done only by one quota at a time.
    """

    def __init__(self, data=None, queryset=None, prefix=None, strict=None):
        super(QuotaFilterMixin, self).__init__(data, queryset, prefix, strict)
        # If projects have to be ordered by quota - we need to filter quotas with given name
        self._prepare_quota_ordering(data)

    def _prepare_quota_ordering(self, data):
        """
        Add filtration by quota if products have to be ordered by quota
        """
        quotas_names = self._meta.model.QUOTAS_NAMES
        quota_filter_map = {'quotas__limit__' + quota_name: quota_name for quota_name in quotas_names}
        quota_filter_map.update(
            {'-quotas__limit__' + quota_name: quota_name for quota_name in quotas_names})
        quota_filter_map.update(
            {'quotas__usage__' + quota_name: quota_name for quota_name in quotas_names})
        quota_filter_map.update(
            {'-quotas__usage__' + quota_name: quota_name for quota_name in quotas_names})

        order_by_input = data.getlist(self.order_by_field)
        if not order_by_input:
            return

        # get all quota args from order data:
        quota_order_by = []
        for order_by in order_by_input:
            if order_by in quota_filter_map:
                quota_order_by.append(order_by)
        if not quota_order_by:
            return

        # only one quota can be used for filtering and sorting:
        first_quota_order_by = quota_order_by[0]
        # filter have to be added to queryset on quota filtering
        quota_name = quota_filter_map[first_quota_order_by]
        self.queryset = self.queryset.filter(quotas__name=quota_name)

        # quota order_by input fields have to be removed and first on have to be replaced with modified:
        order_by_arg = first_quota_order_by.rsplit('__', 1)[0]
        quota_order_by_indexes = [i for i, o in enumerate(order_by_input) if o in quota_order_by]
        # replace first
        order_by_input[quota_order_by_indexes[0]] = order_by_arg
        # remove others
        order_by_input = [
            order_by for i, order_by in enumerate(order_by_input) if i not in quota_order_by_indexes[1:]]

        data.setlist(self.order_by_field, order_by_input)
