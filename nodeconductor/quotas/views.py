from rest_framework import permissions as rf_permissions, exceptions as rf_exceptions

from nodeconductor.core import viewsets as core_viewsets
from nodeconductor.quotas import models, serializers


class QuotaViewSet(core_viewsets.UpdateModelViewSet):

    queryset = models.Quota.objects.all()
    serializer_class = serializers.QuotaSerializer
    lookup_field = 'uuid'
    permission_classes = (rf_permissions.IsAuthenticated,)
    paginate_by = None

    def get_queryset(self):
        return models.Quota.objects.filtered_for_user(self.request.user)

    def pre_save(self, obj):
        super(QuotaViewSet, self).pre_save(obj)
        if not obj.owner.can_user_update_quotas(self.request.user):
            raise rf_exceptions.PermissionDenied()
