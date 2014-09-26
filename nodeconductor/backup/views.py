from rest_framework import permissions as rf_permissions

from nodeconductor.core import viewsets
from nodeconductor.backup import models
from nodeconductor.backup import serializers
from nodeconductor.structure import filters as structure_filters


class BackupScheduleViewSet(viewsets.ModelViewSet):
    model = models.BackupSchedule
    serializer_class = serializers.BackupScheduleSerializer
    lookup_field = 'uuid'
    filter_backends = (structure_filters.GenericRoleFilter,)
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)


class BackupViewSet(viewsets.ModelViewSet):
    model = models.Backup
    serializer_class = serializers.BackupSerializer
    lookup_field = 'uuid'
    filter_backends = (structure_filters.GenericRoleFilter,)
    permission_classes = (rf_permissions.IsAuthenticated,
                          rf_permissions.DjangoObjectPermissions)
