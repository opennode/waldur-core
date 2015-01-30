from rest_framework import permissions as rf_permissions

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
