from __future__ import unicode_literals

from rest_framework import permissions as rf_permissions, exceptions as rf_exceptions, decorators, response, status
from rest_framework import mixins
from rest_framework import viewsets
import reversion
from reversion.models import Version

from nodeconductor.core.filters import DjangoMappingFilterBackend
from nodeconductor.core.pagination import UnlimitedLinkHeaderPagination
from nodeconductor.core.serializers import HistorySerializer
from nodeconductor.core.utils import datetime_to_timestamp
from nodeconductor.quotas import models, serializers, filters


class QuotaViewSet(mixins.UpdateModelMixin,
                   viewsets.ReadOnlyModelViewSet):

    queryset = models.Quota.objects.all()
    serializer_class = serializers.QuotaSerializer
    lookup_field = 'uuid'
    permission_classes = (rf_permissions.IsAuthenticated,)
    # XXX: Remove a custom pagination class once the quota calculation has been made more efficient
    pagination_class = UnlimitedLinkHeaderPagination
    filter_backends = (DjangoMappingFilterBackend, )
    filter_class = filters.QuotaFilterSet

    def get_queryset(self):
        return models.Quota.objects.filtered_for_user(self.request.user)

    def perform_update(self, serializer):
        if not serializer.instance.scope.can_user_update_quotas(self.request.user):
            raise rf_exceptions.PermissionDenied('You do not have permission to perform this action.')
        quota = self.get_object()
        quota_field = quota.get_field()
        # old style quotas do not have quota_field
        if quota_field is not None and quota_field.is_backend:
            raise rf_exceptions.APIException(
                'It is impossible to modify backend quota through this endpoint.',
                status_code=status.HTTP_409_CONFLICT
            )

        limit = serializer.validated_data['limit']
        quota.scope.set_quota_limit(quota.name, limit)

    @decorators.detail_route()
    def history(self, request, uuid=None):
        mapped = {
            'start': request.query_params.get('start'),
            'end': request.query_params.get('end'),
            'points_count': request.query_params.get('points_count'),
            'point_list': request.query_params.getlist('point'),
        }
        history_serializer = HistorySerializer(data={k: v for k, v in mapped.items() if v})
        history_serializer.is_valid(raise_exception=True)

        quota = self.get_object()
        serializer = self.get_serializer(quota)
        serialized_versions = []
        for point_date in history_serializer.get_filter_data():
            serialized = {'point': datetime_to_timestamp(point_date)}
            try:
                version = reversion.get_for_date(quota, point_date)
            except Version.DoesNotExist:
                pass
            else:
                # make copy of serialized data and update field that are stored in version
                version_object = version.object_version.object
                serialized['object'] = serializer.data.copy()
                serialized['object'].update({
                    f: getattr(version_object, f) for f in quota.get_version_fields()
                })
            serialized_versions.append(serialized)
        return response.Response(serialized_versions, status=status.HTTP_200_OK)
